"""LLM node executor for provider-neutral workflow graphs."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from sophos import observability
from sophos.agent.engine import NodeOutcome, WorkflowRun, build_model_transition_tools
from sophos.agent.transcript import NativeEnvelope, Transcript, new_event
from sophos.agent.workflow import NodeSpec, ToolPolicy, WorkflowDefinition
from sophos.llm.provider import CachePlan, LLMProvider, Message, ProviderRequestOptions
from sophos.llm.tool_text import TextualToolCall, call_from_text, normalize_tool_arguments

logger = logging.getLogger(__name__)

ProviderResolver = Callable[[str], LLMProvider]
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[Any]]
ContextRefresher = Callable[[], Awaitable[str | None]]


@dataclass(frozen=True, slots=True)
class AgentTool:
    """Canonical tool schema plus workflow selection metadata."""

    name: str
    category: str
    schema: dict[str, Any]


@dataclass(slots=True)
class LLMWorkflowContext:
    """Raw history with node ownership; each request gets an isolated projection."""

    messages: list[Message]
    tools: tuple[AgentTool, ...]
    provider_resolver: ProviderResolver
    tool_executor: ToolExecutor
    conversation_id: int | None = None
    context_refresher: ContextRefresher | None = None
    max_rounds_per_node: int = 10
    completion_tools: frozenset[str] = field(
        default_factory=lambda: frozenset({"send_message", "finish_without_reply"}),
    )
    system_prompt_renderer: Callable[[NodeSpec], str | None] | None = None
    on_step: Callable[[str, str, dict[str, Any]], None] | None = None
    _message_nodes: dict[int, str] = field(default_factory=dict, init=False, repr=False)

    def append_node_message(self, message: Message, node_id: str) -> None:
        # History is append-only; provenance stays out of provider-visible messages.
        self._message_nodes[len(self.messages)] = node_id
        self.messages.append(message)

    def messages_for_node(self, node_id: str, workflow: WorkflowDefinition) -> list[Message]:
        # Argument-free transitions (e.g. complete_collection) are internal control
        # records. Data-bearing transitions must survive to carry follow-up requests.
        control_tools = {
            node.node_id: {
                tool["function"]["name"] for tool in build_model_transition_tools(workflow, node.node_id)
                if not tool["function"]["parameters"].get("properties")
            }
            for node in workflow.nodes
        }
        projected: list[Message] = []
        visible_call_ids: set[str] = set()
        for index, message in enumerate(self.messages):
            owner = self._message_nodes.get(index)
            if owner is None or owner == node_id:
                # Seed chat, new user messages and this node's own reasoning stay intact.
                projected.append(deepcopy(message))
                continue
            if message.get("role") == "assistant":
                calls = [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call.get("function", {}).get("name", ""),
                            "arguments": deepcopy(call.get("function", {}).get("arguments", "{}")),
                        },
                    }
                    for call in message.get("tool_calls") or []
                    if call.get("function", {}).get("name", "") not in control_tools.get(owner, set())
                ]
                visible_call_ids = {call["id"] for call in calls}
                if calls:
                    # Whitelist protocol fields: no prose, reasoning or native signatures.
                    projected.append({"role": "assistant", "tool_calls": calls})
            elif message.get("role") == "tool" and message.get("tool_call_id") in visible_call_ids:
                projected.append({
                    "role": "tool",
                    "tool_call_id": message["tool_call_id"],
                    "name": message["name"],
                    "content": message.get("content"),
                })
        return projected


class LLMNodeExecutionError(RuntimeError):
    """Raised when an LLM node cannot produce a valid output port."""


class LLMNodeExecutor:
    """Execute any ``kind=llm`` node using its declarative policies."""

    def __init__(self, context: LLMWorkflowContext) -> None:
        self.context = context

    async def __call__(self, node: NodeSpec, run: WorkflowRun) -> NodeOutcome:
        with observability.scope(conversation_id=self.context.conversation_id, run_id=run.run_id):
            return await self._execute(node, run)

    async def _execute(self, node: NodeSpec, run: WorkflowRun) -> NodeOutcome:
        if node.model is None:
            raise LLMNodeExecutionError(f"LLM node has no model policy: {node.node_id}")

        provider = self.context.provider_resolver(node.model.slot)
        selected_tools = _select_tools(self.context.tools, node.tools)
        transition_tools = build_model_transition_tools(run.workflow, node.node_id)
        schemas = [tool.schema for tool in selected_tools] + transition_tools
        transition_names = {tool["function"]["name"] for tool in transition_tools}
        allowed_action_names = {tool.name for tool in selected_tools}
        request_options = ProviderRequestOptions(
            tool_choice="required" if node.model.require_tool_call else "auto",
            strict_tools=True,
            cache=_cache_plan(node, run, self.context.conversation_id),
        )

        max_rounds = node.model.max_tool_rounds or self.context.max_rounds_per_node
        renderer = self.context.system_prompt_renderer
        system_prompt = renderer(node) if renderer is not None else None
        nudged = False
        for round_number in range(1, max_rounds + 1):
            request_messages = _with_node_instructions(
                self.context.messages_for_node(node.node_id, run.workflow),
                node.instructions,
                system_prompt=system_prompt,
            )
            for retry_number in range(4):
                try:
                    response = await observability.chat(
                        provider,
                        request_messages,
                        slot="actor" if node.model.slot == "default" else node.model.slot,
                        tools=schemas,
                        temperature=node.model.temperature,
                        max_tokens=node.model.max_tokens,
                        request_options=request_options,
                    )
                    break
                except (TimeoutError, aiohttp.ClientConnectionError):
                    if retry_number == 3:
                        raise
                    delay = 2**retry_number
                    logger.warning(
                        "LLM request failed in node %s; retrying %d/3 in %ds",
                        node.node_id,
                        retry_number + 1,
                        delay,
                        exc_info=True,
                    )
                    await asyncio.sleep(delay)
            assistant_message = deepcopy(response["message"])
            for index, call in enumerate(assistant_message.get("tool_calls") or []):
                if not call.get("id"):
                    call["id"] = f"{node.node_id}_{run.step_count}_{round_number}_{index}"
            self.context.append_node_message(assistant_message, node.node_id)
            _record_provider_response(run.transcript, node, response)
            _log_model_response(node, round_number, response)
            if self.context.on_step is not None:
                usage = response.get("usage") or {}
                self.context.on_step(
                    "llm_response",
                    node.node_id,
                    {"round": round_number, "output_tokens": usage.get("completion_tokens")},
                )

            tool_calls = assistant_message.get("tool_calls") or []
            if not tool_calls:
                implicit = await self._implicit_outcome(
                    node,
                    assistant_message,
                    allowed_action_names,
                    transition_names,
                    run,
                )
                if implicit is not None:
                    return implicit
                if not nudged and round_number < max_rounds:
                    # 有些提供商忽略 tool_choice=required，只返回文本；追加一次明确提醒再试。
                    nudged = True
                    nudge: Message = {
                        "role": "user",
                        "content": (
                            "系统提示：上一轮没有调用任何工具。请立即调用一个可用工具——"
                            "需要回复用 send_message（必须带上 text 参数写正文，即使只是回复某条消息也要写 text），"
                            "保持沉默用 finish_without_reply，需要流转时调用工作流转换工具；不要只输出文本。"
                        ),
                    }
                    self.context.append_node_message(nudge, node.node_id)
                    run.transcript.append(new_event("message", {"message": nudge}, node_id=node.node_id))
                    logger.info("LLM 节点 %s 未调用工具，追加工具提醒后重试", node.node_id)
                    continue
                logger.warning(
                    "LLM 节点 %s 既没有返回文本也没有调用工具（finish=%s），本轮不会有回复",
                    node.node_id,
                    response.get("finish_reason"),
                )
                raise LLMNodeExecutionError(
                    f"node {node.node_id} returned without a tool or transition call"
                )

            requested_transition: NodeOutcome | None = None
            completion_succeeded = False
            completion_tool = None
            silent_requested = "finish_without_reply" in allowed_action_names and any(
                call.get("function", {}).get("name") == "finish_without_reply" for call in tool_calls
            )
            for index, tool_call in enumerate(tool_calls):
                function = tool_call.get("function", {})
                tool_name = str(function.get("name", ""))
                call_id = str(tool_call.get("id") or f"{node.node_id}_{round_number}_{index}")
                params, parse_error = _parse_arguments(function.get("arguments", "{}"))
                params = normalize_tool_arguments(tool_name, params)
                run.transcript.append(
                    new_event(
                        "tool_call",
                        {"call_id": call_id, "name": tool_name, "arguments": params},
                        node_id=node.node_id,
                    )
                )
                if self.context.on_step is not None:
                    self.context.on_step("tool_call", node.node_id, {"name": tool_name})

                if silent_requested and tool_name != "finish_without_reply":
                    result = {"error": "本轮选择静默结束，其它工具调用已取消"}
                elif parse_error:
                    result: Any = {"error": "工具参数不是合法 JSON，请使用单个 JSON 对象重试"}
                elif tool_name in transition_names:
                    if requested_transition is not None:
                        result = {"error": "同一轮只能请求一个工作流转换"}
                    else:
                        requested_transition = NodeOutcome(tool_name, params)
                        result = {"status": "transition_accepted", "output_port": tool_name}
                elif tool_name not in allowed_action_names:
                    result = {"error": f"工具不在节点允许范围内: {tool_name}"}
                else:
                    try:
                        result = await self.context.tool_executor(tool_name, params)
                    except Exception as exc:
                        await observability.record_error(f"tool:{tool_name}", exc)
                        logger.exception("Tool %s execution failed in node %s", tool_name, node.node_id)
                        result = {"error": f"工具 {tool_name} 执行失败: {exc}"}
                    if isinstance(result, dict) and result.get("error"):
                        logger.warning(
                            "工具 %s 返回错误（node=%s, 参数=%s）：%s",
                            tool_name,
                            node.node_id,
                            _preview(json.dumps(params, ensure_ascii=False, default=str), 300),
                            _preview(str(result.get("error")), 200),
                        )
                    if tool_name in self.context.completion_tools and _is_success(result):
                        completion_succeeded = True
                        completion_tool = tool_name
                        if tool_name == "finish_without_reply":
                            logger.info("模型选择静默结束，本轮不发送回复（node=%s）", node.node_id)

                result_text = json.dumps(result, ensure_ascii=False, default=str)
                self.context.append_node_message(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": result_text,
                    },
                    node.node_id,
                )
                run.transcript.append(
                    new_event(
                        "tool_result",
                        {"call_id": call_id, "name": tool_name, "result": result},
                        node_id=node.node_id,
                    )
                )

            await self._refresh_context(run.transcript, node.node_id)
            if completion_succeeded:
                return NodeOutcome("completed", {"completion_tool": completion_tool})
            if requested_transition is not None:
                return requested_transition

        raise LLMNodeExecutionError(
            f"node {node.node_id} exceeded max_rounds={max_rounds}"
        )

    async def _implicit_outcome(
        self,
        node: NodeSpec,
        assistant_message: Message,
        allowed_action_names: set[str],
        transition_names: set[str],
        run: WorkflowRun,
    ) -> NodeOutcome | None:
        content = str(assistant_message.get("content") or "").strip()
        if not content:
            if len(transition_names) == 1 and "send_message" not in allowed_action_names:
                return NodeOutcome(next(iter(transition_names)), {})
            return None

        # 有些服务商不执行 tool_choice，把 send_message(...) 写成普通文本。
        # 这里解析成真正的调用，避免把调用语法原样发进聊天。
        call = call_from_text(content)
        if call is not None:
            if call.name not in allowed_action_names and call.name not in transition_names:
                logger.warning(
                    "模型把工具调用写成了文本（%s），但不在节点允许范围内，忽略：%s",
                    call.name,
                    _preview(content, 120),
                )
                return None
            return await self._run_textual_call(node, call, run, transition_names)

        if "send_message" in allowed_action_names:
            try:
                result = await self.context.tool_executor("send_message", {"text": content})
            except Exception:
                logger.exception("Implicit send_message failed in node %s", node.node_id)
                return None
            if _is_success(result):
                return NodeOutcome("completed", {"completion_tool": "send_message"})
            return None
        if len(transition_names) == 1 and "send_message" not in allowed_action_names:
            return NodeOutcome(next(iter(transition_names)), {})
        return None

    async def _run_textual_call(
        self,
        node: NodeSpec,
        call: TextualToolCall,
        run: WorkflowRun,
        transition_names: set[str],
    ) -> NodeOutcome | None:
        """执行从文本里解析出来的工具调用，并写入 transcript 便于排查。"""
        call_id = f"{node.node_id}_text_{run.step_count}_{len(self.context.messages)}"
        logger.info("模型把工具调用写成了文本，已解析为真正的调用：%s", call.name)
        run.transcript.append(
            new_event(
                "tool_call",
                {"call_id": call_id, "name": call.name, "arguments": call.arguments},
                node_id=node.node_id,
            )
        )
        if self.context.on_step is not None:
            self.context.on_step("tool_call", node.node_id, {"name": call.name})
        if call.name in transition_names:
            return NodeOutcome(call.name, call.arguments)

        try:
            result = await self.context.tool_executor(call.name, call.arguments)
        except Exception as exc:
            await observability.record_error(f"tool:{call.name}", exc)
            logger.exception("Textual tool %s execution failed in node %s", call.name, node.node_id)
            return None

        run.transcript.append(
            new_event(
                "tool_result",
                {"call_id": call_id, "name": call.name, "result": result},
                node_id=node.node_id,
            )
        )
        if isinstance(result, dict) and result.get("error"):
            logger.warning(
                "文本调用解析后的工具 %s 返回错误（node=%s）：%s",
                call.name,
                node.node_id,
                _preview(str(result.get("error")), 200),
            )
            return None
        return NodeOutcome("completed", {"completion_tool": call.name})

    async def _refresh_context(self, transcript: Transcript, node_id: str) -> None:
        if self.context.context_refresher is None:
            return
        try:
            content = await self.context.context_refresher()
        except Exception:
            logger.warning("Context refresher failed", exc_info=True)
            return
        if not content:
            return
        message: Message = {"role": "user", "content": content}
        self.context.messages.append(message)
        transcript.append(new_event("message", {"message": message}, node_id=node_id))


def transcript_from_messages(messages: list[Message]) -> Transcript:
    """Seed an append-only transcript from an existing chat context."""
    transcript = Transcript()
    for message in messages:
        transcript.append(new_event("message", {"message": message}))
    return transcript


def _select_tools(tools: tuple[AgentTool, ...], policy: ToolPolicy) -> tuple[AgentTool, ...]:
    categories = set(policy.include_categories)
    names = set(policy.include_names)
    excluded = set(policy.exclude_names)
    if not categories and not names:
        selected = list(tools)
    else:
        selected = [tool for tool in tools if tool.category in categories or tool.name in names]
    return tuple(tool for tool in selected if tool.name not in excluded)


def _with_node_instructions(
    messages: list[Message],
    instructions: str,
    *,
    system_prompt: str | None = None,
) -> list[Message]:
    """Create a node-specific request view while leaving shared history untouched."""
    projected = [dict(message) for message in messages]
    if projected and projected[0].get("role") == "system":
        if system_prompt is not None:
            projected[0]["content"] = system_prompt
    else:
        projected.insert(0, {"role": "system", "content": system_prompt or ""})
    if instructions:
        stage_block = f"\n\n---\n[当前工作流节点指令]\n{instructions}"
        projected[0]["content"] = str(projected[0].get("content") or "") + stage_block
    return projected


def _cache_plan(node: NodeSpec, run: WorkflowRun, conversation_id: int | None) -> CachePlan | None:
    if not node.cache.enabled:
        return None
    components = [run.workflow.workflow_id, run.workflow.revision]
    if node.cache.scope in {"node", "conversation", "principal"}:
        components.append(node.node_id)
    if node.cache.scope == "conversation" and conversation_id is not None:
        components.append(str(conversation_id))
    return CachePlan(
        key=":".join(components),
        preferred_ttl_seconds=node.cache.preferred_ttl_seconds,
    )


def _parse_arguments(raw: Any) -> tuple[dict[str, Any], bool]:
    if isinstance(raw, dict):
        return raw, False
    try:
        parsed = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}, True
    return (parsed, False) if isinstance(parsed, dict) else ({}, True)


def _is_success(result: Any) -> bool:
    return not (isinstance(result, dict) and result.get("error"))


def _preview(text: str, limit: int = 300) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[:limit] + "…"


def _log_model_response(node: NodeSpec, round_number: int, response: dict[str, Any]) -> None:
    """把模型这一轮的输出写进日志，便于排查「为什么不回复」。"""
    message = response.get("message") or {}
    content = str(message.get("content") or "")
    calls = message.get("tool_calls") or []
    tool_names = [str((call.get("function") or {}).get("name") or "?") for call in calls]
    usage = response.get("usage") or {}
    logger.info(
        "LLM 响应 node=%s round=%d finish=%s content_len=%d tools=%s output_tokens=%s",
        node.node_id,
        round_number,
        response.get("finish_reason"),
        len(content),
        tool_names or "-",
        usage.get("completion_tokens"),
    )
    if content:
        logger.info("LLM 文本预览 node=%s: %s", node.node_id, _preview(content))


def _record_provider_response(
    transcript: Transcript,
    node: NodeSpec,
    response: dict[str, Any],
) -> None:
    provider = str(response.get("provider") or "unknown")
    metadata = dict(response.get("native_metadata") or {})
    native = NativeEnvelope(
        provider=provider,
        api_surface="chat",
        model=str(metadata.get("model")) if metadata.get("model") is not None else None,
        payload=metadata,
    )
    transcript.append(
        new_event(
            "provider_response",
            {
                "message": response.get("message", {}),
                "usage": response.get("usage"),
                "finish_reason": response.get("finish_reason"),
            },
            node_id=node.node_id,
            native_envelopes=(native,),
        )
    )
