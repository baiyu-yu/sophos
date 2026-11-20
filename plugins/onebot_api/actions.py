"""SnowLuma OneBot 动作目录（自动生成，请勿手改）。

来源：@snowluma/mcp 的 dist/generated/catalog.js。
重新生成：python plugins/onebot_api/gen_catalog.py <catalog.json>
具体字段含义见 gen_catalog.py 的模块文档。
"""

# ruff: noqa: E501

from __future__ import annotations

from typing import Any

CATALOG_SOURCE = "snowluma-mcp@2.4.2"

CATALOG_SIZE = 222

CATEGORIES: tuple[str, ...] = (
    "信息",
    "消息",
    "好友",
    "群信息",
    "群管理",
    "群文件",
    "请求",
    "扩展",
    "群相册",
    "空间",
    "系统表情",
    "流式接口",
)

CATEGORY_ACTIONS: dict[str, tuple[str, ...]] = {
    "信息": ("can_send_image", "can_send_record", "get_login_info", "get_status", "get_version_info"),
    "消息": ("delete_msg", "get_msg", "send_custom_face", "send_group_msg", "send_msg", "send_private_msg"),
    "好友": ("delete_friend", "get_friend_list", "get_stranger_info"),
    "群信息": ("get_group_honor_info", "get_group_info", "get_group_list", "get_group_member_info", "get_group_member_list", "get_group_share_link", "get_group_system_msg"),
    "群管理": ("add_group_tag", "delete_group_tag", "get_group_admin_permissions", "get_group_admin_settings", "get_group_tags", "set_group_add_option", "set_group_admin", "set_group_admin_permissions", "set_group_admin_receive_verify", "set_group_anonymous", "set_group_anonymous_ban", "set_group_ban", "set_group_card", "set_group_kick", "set_group_kick_members", "set_group_leave", "set_group_member_invite_policy", "set_group_member_permissions", "set_group_name", "set_group_new_member_history_visibility", "set_group_portrait", "set_group_search", "set_group_special_title", "set_group_whole_ban"),
    "群文件": ("create_group_file_folder", "delete_group_file", "delete_group_file_folder", "get_group_file_url", "get_group_files_by_folder", "get_group_root_files", "get_private_file_url", "move_group_file", "rename_group_file", "rename_group_file_folder", "upload_group_file", "upload_private_file"),
    "请求": ("set_friend_add_request", "set_group_add_request"),
    "扩展": (".get_word_slices", "_del_group_notice", "_get_friend_dress", "_get_group_notice", "_get_model_show", "_mark_all_as_read", "_send_group_notice", "_set_model_show", "add_custom_face", "bot_exit", "cancel_group_todo", "check_url_safely", "clean_cache", "click_inline_keyboard_button", "complete_group_todo", "create_collection", "create_flash_task", "delete_custom_face", "delete_essence_msg", "delete_flash_file", "delete_group_folder", "download_file", "download_fileset", "fetch_custom_face", "fetch_custom_face_detail", "fetch_emoji_like", "fetch_ptt_text", "forward_friend_single_msg", "forward_group_single_msg", "friend_poke", "get_ai_characters", "get_ai_record", "get_clientkey", "get_collection_list", "get_cookies", "get_credentials", "get_csrf_token", "get_doubt_friends_add_request", "get_emoji_likes", "get_essence_msg_list", "get_file", "get_fileset_id", "get_fileset_info", "get_flash_file_list", "get_flash_file_url", "get_forward_msg", "get_friend_msg_history", "get_friends_with_category", "get_group_at_all_remain", "get_group_detail_info", "get_group_file_system_info", "get_group_ignore_add_request", "get_group_ignored_notifies", "get_group_info_ex", "get_group_msg_history", "get_group_shut_list", "get_group_signed_list", "get_group_todo_list", "get_image", "get_mini_app_ark", "get_msg_emoji_likes", "get_online_clients", "get_profile_like", "get_recent_contact", "get_record", "get_rkey", "get_rkey_server", "get_share_link", "get_unidirectional_friend_list", "group_poke", "list_filesets", "mark_group_msg_as_read", "mark_msg_as_read", "mark_private_msg_as_read", "modify_custom_face", "move_custom_face_to_front", "nc_get_packet_status", "nc_get_user_status", "ocr_image", "rename_flash_file", "request_decrypt_key", "send_ark_share", "send_flash_msg", "send_forward_msg", "send_group_ai_record", "send_group_ark_share", "send_group_forward_msg", "send_like", "send_packet", "send_poke", "send_private_forward_msg", "send_tuwen_ark", "set_diy_online_status", "set_doubt_friends_add_request", "set_essence_msg", "set_friend_remark", "set_friends_category", "set_group_reaction", "set_group_remark", "set_group_robot_add_option", "set_group_sign", "set_group_todo", "set_input_status", "set_msg_emoji_like", "set_online_status", "set_qq_avatar", "set_qq_profile", "set_restart", "set_self_longnick", "share_group_ex", "share_peer", "trans_group_file", "translate_en2zh", "upload_forward_msg", "upload_foward_msg"),
    "群相册": ("cancel_group_album_media_like", "del_group_album_media", "do_group_album_comment", "get_group_album_list", "get_group_album_media_list", "get_qun_album_list", "set_group_album_media_like", "upload_image_to_qun_album", "upload_video_to_qun_album"),
    "空间": ("comment_qzone", "comment_qzone_public_feed", "delete_qzone_msg", "delete_qzone_public_comment", "delete_qzone_public_reply", "forward_qzone_public_feed", "get_qzone_feed_detail", "get_qzone_feeds", "get_qzone_home_feeds", "get_qzone_msg_detail", "get_qzone_msg_list", "get_qzone_profile", "get_qzone_public_capabilities", "get_qzone_public_comments", "get_qzone_public_feed_detail", "get_qzone_public_feeds", "get_qzone_public_replies", "get_qzone_share_ark", "like_qzone", "reply_qzone_public_feed", "send_qzone_msg", "set_qzone_ban", "set_qzone_msg_right", "set_qzone_profile", "set_qzone_public_comment_like", "set_qzone_public_follow", "set_qzone_public_like", "set_qzone_public_upvote", "unlike_qzone"),
    "系统表情": ("fetch_face_entity", "fetch_super_face_id", "fetch_sys_faces", "search_sys_faces"),
    "流式接口": ("clean_stream_temp_file", "download_file_image_stream", "download_file_record_stream", "download_file_stream", "test_download_stream", "upload_file_stream"),
}

# name -> {summary, read_only, category, aliases, params[(name, required, type, role, desc)]}
ACTIONS: dict[str, dict[str, Any]] = {
    ".get_word_slices": {
        "summary": "分词（未实现）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "_del_group_notice": {
        "summary": "删除群公告（fid 或 notice_id 二选一）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("fid", False, "string", "", ""),
            ("notice_id", False, "string", "", ""),
        ),
    },
    "_get_friend_dress": {
        "summary": "获取指定 QQ 号正在使用的个性装扮（挂件/名片/来电/输入状态等）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", "目标 QQ 号"),
        ),
    },
    "_get_group_notice": {
        "summary": "获取群公告",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "_get_model_show": {
        "summary": "获取机型展示（兼容 mock）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("model", False, "string", "", ""),
        ),
    },
    "_mark_all_as_read": {
        "summary": "标记全部已读",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "_send_group_notice": {
        "summary": "发送群公告（支持置顶、弹窗、新成员、群昵称引导与确认）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("content", True, "string", "", "公告正文"),
            ("image", False, "string", "image", "可选公告图片（本地路径、URL 或 base64）"),
            ("pinned", False, "int", "", "是否置顶：1=置顶，0=不置顶"),
            ("type", False, "int", "", "发布类型：1=普通公告，20=新成员公告；建议使用 send_to_new_members"),
            ("send_to_new_members", False, "bool", "", "是否在成员新加入群时发送（与 type=20 等价）"),
            ("is_show_edit_card", False, "int", "", "是否引导群成员修改群昵称：1=是，0=否"),
            ("tip_window_type", False, "int", "", "弹窗展示：0=开启弹窗，1=关闭弹窗（QQ 原始字段为反向语义）"),
            ("confirm_required", False, "int", "", "是否需要群成员确认收到：1=是，0=否"),
        ),
    },
    "_set_model_show": {
        "summary": "设置机型展示（占位）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "add_custom_face": {
        "summary": "添加收藏表情",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("file", True, "string", "image", ""),
        ),
    },
    "add_group_tag": {
        "summary": "向某个群分类添加资料标签",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_class", True, "int", "", ""),
            ("name", True, "string", "", ""),
        ),
    },
    "bot_exit": {
        "summary": "退出机器人",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "can_send_image": {
        "summary": "",
        "read_only": True,
        "category": "信息",
        "aliases": (),
        "params": (
        ),
    },
    "can_send_record": {
        "summary": "",
        "read_only": True,
        "category": "信息",
        "aliases": (),
        "params": (
        ),
    },
    "cancel_group_album_media_like": {
        "summary": "",
        "read_only": False,
        "category": "群相册",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("album_id", True, "string", "", ""),
            ("batch_id", True, "string", "", ""),
            ("lloc", False, "string", "", ""),
        ),
    },
    "cancel_group_todo": {
        "summary": "取消群待办",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("message_id", True, "messageId", "message_id", ""),
        ),
    },
    "check_url_safely": {
        "summary": "检查链接安全性",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "clean_cache": {
        "summary": "清理缓存",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "clean_stream_temp_file": {
        "summary": "清理流式传输临时文件(仅清理 stream 上传/下载目录)",
        "read_only": False,
        "category": "流式接口",
        "aliases": (),
        "params": (
        ),
    },
    "click_inline_keyboard_button": {
        "summary": "点击内联键盘按钮",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("bot_appid", True, "uint", "", ""),
            ("msg_seq", True, "uint", "", ""),
            ("button_id", True, "string", "", ""),
            ("callback_data", False, "string", "", ""),
        ),
    },
    "comment_qzone": {
        "summary": "评论说说或回复指定评论（普通评论支持带图，楼中楼仅支持文字）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("tid", True, "string", "", "说说 tid"),
            ("content", True, "string", "", "评论内容"),
            ("target_uin", False, "uint", "user_id", "说说所属 QQ 号，省略则为机器人自己"),
            ("comment_id", False, "string", "", "一级父评论 ID，与 comment_uin 同时提供；编号 0 有效，不能传二级回复自身的 ID"),
            ("comment_uin", False, "uint", "user_id", "一级父评论作者 QQ 号，与 comment_id 同时提供；不是说说所属账号"),
            ("reply_uin", False, "uint", "user_id", "楼中楼中要回复的用户 QQ 号，与 reply_name 同时提供，需指定父评论"),
            ("reply_name", False, "string", "", "要回复的用户昵称，来自评论详情的 name；与 reply_uin 同时提供"),
            ("images", False, "string[]", "", "图片数组（可选），支持 file:// http:// base64://；自动上传"),
        ),
    },
    "comment_qzone_public_feed": {
        "summary": "评论推荐动态，支持文本或上游富文本条目",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("content", True, "string | object[]", "", "非空文本，或非空上游 RichItem 对象数组；字符串始终原样发送，富文本请直接传对象数组，不是 OneBot 消息段"),
        ),
    },
    "complete_group_todo": {
        "summary": "完成群待办",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("message_id", True, "messageId", "message_id", ""),
        ),
    },
    "create_collection": {
        "summary": "创建收藏（未实现）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "create_flash_task": {
        "summary": "创建闪传任务",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("files", False, "raw", "", "路径、{ file, name }，或它们的数组"),
            ("name", False, "string", "", ""),
            ("thumb_path", False, "string", "", ""),
        ),
    },
    "create_group_file_folder": {
        "summary": "创建群文件夹",
        "read_only": False,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("name", True, "string", "", ""),
            ("parent_id", False, "string", "", ""),
        ),
    },
    "del_group_album_media": {
        "summary": "删除群相册图片或视频",
        "read_only": False,
        "category": "群相册",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("album_id", True, "string", "", ""),
            ("lloc", True, "string", "", "图片长定位标识，或视频 id"),
        ),
    },
    "delete_custom_face": {
        "summary": "删除收藏表情",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("emoji_id", True, "string", "", ""),
        ),
    },
    "delete_essence_msg": {
        "summary": "移除精华消息",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
        ),
    },
    "delete_flash_file": {
        "summary": "删除闪传文件",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("fileset_id", True, "string", "", ""),
        ),
    },
    "delete_friend": {
        "summary": "删除好友",
        "read_only": False,
        "category": "好友",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", "QQ 号"),
            ("block", False, "bool", "", ""),
        ),
    },
    "delete_group_file": {
        "summary": "删除群文件",
        "read_only": False,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("file_id", True, "string", "file_id", ""),
        ),
    },
    "delete_group_file_folder": {
        "summary": "删除群文件夹",
        "read_only": False,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("folder_id", True, "string", "", ""),
        ),
    },
    "delete_group_folder": {
        "summary": "删除群文件夹",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("folder_id", True, "string", "", ""),
        ),
    },
    "delete_group_tag": {
        "summary": "从某个群分类移除资料标签",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_class", True, "int", "", ""),
            ("name", True, "string", "", ""),
        ),
    },
    "delete_msg": {
        "summary": "撤回消息",
        "read_only": False,
        "category": "消息",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
        ),
    },
    "delete_qzone_msg": {
        "summary": "删除一条说说（QQ 空间，按 tid）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("tid", True, "string", "", "说说 tid（来自 get_qzone_msg_list / send_qzone_msg）"),
        ),
    },
    "delete_qzone_public_comment": {
        "summary": "删除推荐动态的一条评论（需有权限）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("comment", True, "object", "", "详情或评论页返回的完整评论对象，保留 user 等原始字段"),
        ),
    },
    "delete_qzone_public_reply": {
        "summary": "删除推荐动态评论下的一条回复（需有权限）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("comment", True, "object", "", "详情或评论页返回的完整评论对象，保留 user 等原始字段"),
            ("reply", True, "object", "", "评论或回复页返回的完整回复对象，保留 user 等原始字段"),
        ),
    },
    "do_group_album_comment": {
        "summary": "",
        "read_only": False,
        "category": "群相册",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("album_id", True, "string", "", ""),
            ("lloc", True, "string", "", ""),
            ("content", True, "string", "", ""),
        ),
    },
    "download_file": {
        "summary": "下载文件（url 或 base64）到 data/downloads",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("url", False, "string", "", ""),
            ("base64", False, "string", "", ""),
            ("name", False, "string", "", ""),
            ("headers", False, "raw", "", ""),
        ),
    },
    "download_file_image_stream": {
        "summary": "以流式方式下载图片(缓存图片 id / URL / stream 目录本地文件)",
        "read_only": False,
        "category": "流式接口",
        "aliases": (),
        "params": (
            ("file", False, "string", "file", "文件路径(限 stream 临时目录)/ http(s) URL"),
            ("file_id", False, "string", "file_id", "文件 ID(缓存的图片/语音 id)"),
            ("chunk_size", False, "int", "", "分块大小(字节,默认 64KB)"),
        ),
    },
    "download_file_record_stream": {
        "summary": "以流式方式下载语音(缓存语音 id / URL / stream 目录本地文件)",
        "read_only": False,
        "category": "流式接口",
        "aliases": (),
        "params": (
            ("file", False, "string", "file", "文件路径(限 stream 临时目录)/ http(s) URL"),
            ("file_id", False, "string", "file_id", "文件 ID(缓存的图片/语音 id)"),
            ("chunk_size", False, "int", "", "分块大小(字节,默认 64KB)"),
        ),
    },
    "download_file_stream": {
        "summary": "以流式方式下载文件(stream 目录本地文件 / URL / 缓存媒体)",
        "read_only": False,
        "category": "流式接口",
        "aliases": (),
        "params": (
            ("file", False, "string", "file", "文件路径(限 stream 临时目录)/ http(s) URL"),
            ("file_id", False, "string", "file_id", "文件 ID(缓存的图片/语音 id)"),
            ("chunk_size", False, "int", "", "分块大小(字节,默认 64KB)"),
        ),
    },
    "download_fileset": {
        "summary": "解析闪传文件下载直链（不下载，由调用方实现下载）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("fileset_id", True, "string", "", ""),
            ("file_name", False, "string", "", ""),
            ("file_index", False, "number", "", ""),
        ),
    },
    "fetch_custom_face": {
        "summary": "获取自定义表情",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("count", False, "int", "", ""),
            ("return_type", False, "string", "", ""),
        ),
    },
    "fetch_custom_face_detail": {
        "summary": "获取自定义表情详情",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("count", False, "int", "", ""),
        ),
    },
    "fetch_emoji_like": {
        "summary": "获取表情回应用户（NapCat 分页）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
            ("emojiId", True, "string", "", ""),
            ("count", False, "int", "", ""),
            ("cookie", False, "string", "", ""),
        ),
    },
    "fetch_face_entity": {
        "summary": "按编号查询 QQ 系统表情",
        "read_only": True,
        "category": "系统表情",
        "aliases": (),
        "params": (
            ("face_id", True, "int", "face_id", "QQ 系统表情编号"),
            ("refresh", False, "bool", "", "是否强制从 QQ 刷新目录"),
        ),
    },
    "fetch_ptt_text": {
        "summary": "获取语音转文字结果",
        "read_only": True,
        "category": "扩展",
        "aliases": ("get_ptt_text","get_record_text",),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
        ),
    },
    "fetch_super_face_id": {
        "summary": "判断 QQ 系统表情是否使用超级表情格式",
        "read_only": True,
        "category": "系统表情",
        "aliases": (),
        "params": (
            ("face_id", True, "int", "face_id", "QQ 系统表情编号"),
            ("refresh", False, "bool", "", "是否强制从 QQ 刷新目录"),
        ),
    },
    "fetch_sys_faces": {
        "summary": "获取 QQ 系统表情目录",
        "read_only": True,
        "category": "系统表情",
        "aliases": (),
        "params": (
            ("refresh", False, "bool", "", "是否强制从 QQ 刷新目录"),
        ),
    },
    "forward_friend_single_msg": {
        "summary": "转发单条消息给好友",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
            ("user_id", True, "uint", "user_id", ""),
        ),
    },
    "forward_group_single_msg": {
        "summary": "转发单条消息到群",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
            ("group_id", True, "uint", "group_id", ""),
        ),
    },
    "forward_qzone_public_feed": {
        "summary": "将推荐动态转发到当前账号空间",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("reason", False, "string", "", "转发附言，可为空"),
        ),
    },
    "friend_poke": {
        "summary": "好友拍一拍",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
            ("target_id", False, "uint", "user_id", ""),
        ),
    },
    "get_ai_characters": {
        "summary": "获取 AI 语音角色",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("chat_type", False, "int", "", ""),
        ),
    },
    "get_ai_record": {
        "summary": "生成 AI 语音",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("character", True, "string", "", ""),
            ("text", True, "string", "", ""),
            ("chat_type", False, "int", "", ""),
        ),
    },
    "get_clientkey": {
        "summary": "获取 clientkey",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "get_collection_list": {
        "summary": "获取收藏列表",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("category", False, "int", "", "收藏分类 ID；0 表示全部分类"),
            ("count", False, "int", "", "最多返回的收藏数量"),
        ),
    },
    "get_cookies": {
        "summary": "获取 Cookies",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("domain", False, "string", "", ""),
        ),
    },
    "get_credentials": {
        "summary": "获取凭证",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("domain", False, "string", "", ""),
        ),
    },
    "get_csrf_token": {
        "summary": "获取 CSRF 令牌",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "get_doubt_friends_add_request": {
        "summary": "获取可疑好友申请",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("count", False, "int", "", ""),
        ),
    },
    "get_emoji_likes": {
        "summary": "获取表情回应用户",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
            ("emoji_id", True, "string", "", ""),
        ),
    },
    "get_essence_msg_list": {
        "summary": "获取精华消息列表",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "get_file": {
        "summary": "获取文件信息（仅图片/语音缓存；群文件请用 get_group_file_url）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("file_id", False, "string", "file_id", ""),
            ("file", False, "string", "file", ""),
        ),
    },
    "get_fileset_id": {
        "summary": "从 QQ 闪传分享码或官方分享链接获取 fileset_id",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("share_code", True, "string", "", "QQ 闪传分享码，或 https://qfile.qq.com/q/... 官方分享链接"),
        ),
    },
    "get_fileset_info": {
        "summary": "获取文件集信息",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("fileset_id", True, "string", "", ""),
        ),
    },
    "get_flash_file_list": {
        "summary": "获取闪传文件列表",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("fileset_id", True, "string", "", ""),
        ),
    },
    "get_flash_file_url": {
        "summary": "获取闪传文件链接",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("fileset_id", True, "string", "", ""),
            ("file_name", False, "string", "", ""),
            ("file_index", False, "number", "", ""),
        ),
    },
    "get_forward_msg": {
        "summary": "获取合并转发消息（id 或 message_id）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("id", False, "string", "", ""),
            ("message_id", False, "string", "", ""),
        ),
    },
    "get_friend_list": {
        "summary": "获取好友列表",
        "read_only": True,
        "category": "好友",
        "aliases": (),
        "params": (
            ("with_profile", False, "bool", "", "主动补查好友公开资料，按账号缓存五分钟；大列表可能耗时较长"),
        ),
    },
    "get_friend_msg_history": {
        "summary": "获取好友消息历史（无锚点时从服务器获取最新双向记录）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
            ("message_id", False, "int", "message_id", ""),
            ("count", False, "int", "", "无锚点时从 QQ 服务器获取最新双向历史；服务器或身份解析失败时动作失败，不返回不完整的本地缓存"),
            ("reverse_order", False, "bool", "", "仅在 message_id 非 0 时生效；true 返回锚点及更旧消息，false 返回锚点及更新消息"),
        ),
    },
    "get_friends_with_category": {
        "summary": "获取分组好友列表",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("with_profile", False, "bool", "", "主动补查好友公开资料，按账号缓存五分钟；大列表可能耗时较长"),
        ),
    },
    "get_group_admin_permissions": {
        "summary": "读取指定管理员的撤回、移除成员、每日移除上限及接收验证消息状态",
        "read_only": True,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
        ),
    },
    "get_group_admin_settings": {
        "summary": "获取群管理设置的当前值",
        "read_only": True,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "get_group_album_list": {
        "summary": "",
        "read_only": True,
        "category": "群相册",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "get_group_album_media_list": {
        "summary": "",
        "read_only": True,
        "category": "群相册",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("album_id", True, "string", "", ""),
            ("attach_info", False, "string", "", ""),
        ),
    },
    "get_group_at_all_remain": {
        "summary": "获取群 @全体成员 剩余次数",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "get_group_detail_info": {
        "summary": "获取群详细信息",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", ""),
            ("no_cache", False, "bool", "", ""),
        ),
    },
    "get_group_file_system_info": {
        "summary": "获取群文件系统信息",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "get_group_file_url": {
        "summary": "获取群文件下载链接",
        "read_only": True,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("file_id", True, "string", "file_id", ""),
            ("busid", False, "raw", "", ""),
        ),
    },
    "get_group_files_by_folder": {
        "summary": "获取群子目录文件列表",
        "read_only": True,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("folder_id", False, "string", "", ""),
            ("folder", False, "string", "", ""),
        ),
    },
    "get_group_honor_info": {
        "summary": "获取群荣誉信息",
        "read_only": True,
        "category": "群信息",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("type", False, "string", "", ""),
        ),
    },
    "get_group_ignore_add_request": {
        "summary": "获取被忽略的入群请求（NapCat）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "get_group_ignored_notifies": {
        "summary": "获取被过滤的入群请求",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "get_group_info": {
        "summary": "获取群信息",
        "read_only": True,
        "category": "群信息",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("no_cache", False, "bool", "", ""),
        ),
    },
    "get_group_info_ex": {
        "summary": "获取群信息（扩展）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", ""),
            ("no_cache", False, "bool", "", ""),
        ),
    },
    "get_group_list": {
        "summary": "获取群列表",
        "read_only": True,
        "category": "群信息",
        "aliases": (),
        "params": (
            ("no_cache", False, "bool", "", ""),
        ),
    },
    "get_group_member_info": {
        "summary": "获取群成员信息",
        "read_only": True,
        "category": "群信息",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
            ("no_cache", False, "bool", "", ""),
        ),
    },
    "get_group_member_list": {
        "summary": "获取群成员列表",
        "read_only": True,
        "category": "群信息",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("no_cache", False, "bool", "", ""),
        ),
    },
    "get_group_msg_history": {
        "summary": "获取群消息历史",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("message_id", False, "int", "message_id", ""),
            ("count", False, "int", "", ""),
            ("reverse_order", False, "bool", "", "仅在 message_id 非 0 时生效；true 返回锚点及更旧消息，false 返回锚点及更新消息"),
        ),
    },
    "get_group_root_files": {
        "summary": "获取群根目录文件列表",
        "read_only": True,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "get_group_share_link": {
        "summary": "获取群分享链接",
        "read_only": True,
        "category": "群信息",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("need_short_url", False, "bool", "", "是否获取短链接"),
            ("src_id", False, "int", "", "来源标识（兼容参数）"),
            ("additional_param", False, "string", "", "附加参数"),
        ),
    },
    "get_group_shut_list": {
        "summary": "获取群禁言列表",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "get_group_signed_list": {
        "summary": "获取群今日打卡列表",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "get_group_system_msg": {
        "summary": "获取群系统消息",
        "read_only": True,
        "category": "群信息",
        "aliases": (),
        "params": (
            ("group_id", False, "uint", "group_id", ""),
            ("only_pending", False, "bool", "", ""),
            ("count", False, "int", "", "每个收件箱最多读取的记录数"),
        ),
    },
    "get_group_tags": {
        "summary": "读取某个群分类下的资料标签",
        "read_only": True,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_class", True, "int", "", ""),
        ),
    },
    "get_group_todo_list": {
        "summary": "获取群待办列表",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "get_image": {
        "summary": "获取图片信息",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("file", False, "string", "image", ""),
            ("file_id", False, "string", "file_id", ""),
        ),
    },
    "get_login_info": {
        "summary": "",
        "read_only": True,
        "category": "信息",
        "aliases": (),
        "params": (
        ),
    },
    "get_mini_app_ark": {
        "summary": "获取小程序卡片 ark",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("type", False, "string", "", ""),
            ("title", False, "string", "", ""),
            ("desc", False, "string", "", ""),
            ("picUrl", False, "string", "", ""),
            ("pic_url", False, "string", "", ""),
            ("jumpUrl", False, "string", "", ""),
            ("jump_url", False, "string", "", ""),
        ),
    },
    "get_msg": {
        "summary": "获取消息",
        "read_only": True,
        "category": "消息",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
        ),
    },
    "get_msg_emoji_likes": {
        "summary": "获取一条消息的全部表情回应",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
        ),
    },
    "get_online_clients": {
        "summary": "获取在线客户端",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("no_cache", False, "bool", "", "是否强制刷新；QQ 当前仅暴露本地快照，true 会明确失败"),
        ),
    },
    "get_private_file_url": {
        "summary": "获取私聊文件下载链接",
        "read_only": True,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("user_id", False, "uint", "user_id", ""),
            ("file_id", True, "string", "file_id", ""),
            ("file_hash", False, "string", "", ""),
        ),
    },
    "get_profile_like": {
        "summary": "获取资料点赞",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", False, "int", "user_id", ""),
            ("start", False, "int", "", ""),
            ("count", False, "int", "", ""),
        ),
    },
    "get_qun_album_list": {
        "summary": "",
        "read_only": True,
        "category": "群相册",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("attach_info", False, "string", "", ""),
        ),
    },
    "get_qzone_feed_detail": {
        "summary": "按说说 tid 读取完整空间动态，可用于生成分享卡片",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("tid", True, "string", "", "24 位十六进制说说编号"),
        ),
    },
    "get_qzone_feeds": {
        "summary": "获取 QQ 空间好友动态，支持结构化正文与游标分页",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("page_num", False, "int", "", "页码（1 起）；不传 cursor 时从首页顺序定位，较深页可能耗时较长"),
            ("count", False, "int", "", "本页数量"),
            ("cursor", False, "string", "", "上一次返回的 next_cursor；原样传递，省略 page_num 或传入对应页码"),
        ),
    },
    "get_qzone_home_feeds": {
        "summary": "读取自己或有权访问的空间主页动态，保留完整分享信息",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("target_uin", False, "uint", "user_id", "主页所属 QQ 号，省略则为当前账号"),
            ("cursor", False, "string", "", "上次返回的 next_cursor，仅限同一账号及主页"),
        ),
    },
    "get_qzone_msg_detail": {
        "summary": "获取 QQ 空间说说详情与一页评论（含服务端内联回复，需有访问权限）",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("tid", True, "string", "", "说说 tid（来自 get_qzone_msg_list / send_qzone_msg）"),
            ("target_uin", False, "uint", "user_id", "说说所属 QQ 号，省略则取机器人自己"),
            ("pos", False, "int", "", "一级评论起始偏移"),
            ("num", False, "int", "", "请求的一级评论数量，实际数量受服务端限制"),
        ),
    },
    "get_qzone_msg_list": {
        "summary": "获取 QQ 空间说说列表（默认机器人自己的空间）",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("target_uin", False, "uint", "user_id", "目标 QQ 号，省略则取机器人自己"),
            ("pos", False, "int", "", "起始偏移"),
            ("num", False, "int", "", "本页数量"),
        ),
    },
    "get_qzone_profile": {
        "summary": "获取 QQ 空间名称和说明（默认当前账号）",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("target_uin", False, "uint", "user_id", "目标 QQ 号，省略则取机器人自己"),
        ),
    },
    "get_qzone_public_capabilities": {
        "summary": "读取当前账号的空友爱看入口与推权限",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
        ),
    },
    "get_qzone_public_comments": {
        "summary": "继续读取推荐动态评论",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("cursor", True, "string", "", "详情或上一评论页返回的 attach_info"),
        ),
    },
    "get_qzone_public_feed_detail": {
        "summary": "读取推荐动态详情及初始评论",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
        ),
    },
    "get_qzone_public_feeds": {
        "summary": "读取空友爱看推荐动态，支持独立游标分页",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("cursor", False, "string", "", "上次返回的 next_cursor，省略则刷新首页"),
        ),
    },
    "get_qzone_public_replies": {
        "summary": "继续读取指定评论的回复",
        "read_only": True,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("comment", True, "object", "", "详情或评论页返回的完整评论对象，保留 user 等原始字段"),
            ("cursor", False, "string", "", "上一回复页的 reply_attach_info；省略则使用评论自带游标"),
            ("page_size", False, "int", "", "请求的回复数量"),
        ),
    },
    "get_qzone_share_ark": {
        "summary": "生成空间动态分享卡片，返回原文及分享提示",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "主页、详情或推荐列表返回的完整动态，保留所有原始字段"),
        ),
    },
    "get_recent_contact": {
        "summary": "获取最近会话（占位）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("count", False, "int", "", ""),
        ),
    },
    "get_record": {
        "summary": "获取语音信息；传 out_format 则服务端转码并附带 base64",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("file", False, "string", "record", ""),
            ("file_id", False, "string", "file_id", ""),
            ("out_format", False, "enum", "", ""),
        ),
    },
    "get_rkey": {
        "summary": "获取下载 rkey",
        "read_only": True,
        "category": "扩展",
        "aliases": ("nc_get_rkey",),
        "params": (
        ),
    },
    "get_rkey_server": {
        "summary": "获取 rkey 服务器信息",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "get_share_link": {
        "summary": "获取文件分享链接",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("fileset_id", True, "string", "", ""),
        ),
    },
    "get_status": {
        "summary": "",
        "read_only": True,
        "category": "信息",
        "aliases": (),
        "params": (
        ),
    },
    "get_stranger_info": {
        "summary": "获取陌生人信息",
        "read_only": True,
        "category": "好友",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", "QQ 号"),
        ),
    },
    "get_unidirectional_friend_list": {
        "summary": "获取单向好友列表",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "get_version_info": {
        "summary": "",
        "read_only": True,
        "category": "信息",
        "aliases": (),
        "params": (
        ),
    },
    "group_poke": {
        "summary": "群拍一拍",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
        ),
    },
    "like_qzone": {
        "summary": "给一条说说点赞（QQ 空间）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("tid", True, "string", "", "说说 tid"),
            ("target_uin", False, "uint", "user_id", "说说所属 QQ 号，省略则为机器人自己"),
            ("abstime", False, "int", "timestamp", "说说发表时间（unix 秒），传真实值更可靠"),
        ),
    },
    "list_filesets": {
        "summary": "列出当前账号的所有闪传文件集",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "mark_group_msg_as_read": {
        "summary": "标记群消息已读",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
            ("group_id", False, "uint", "group_id", ""),
        ),
    },
    "mark_msg_as_read": {
        "summary": "标记消息已读（群聊/私聊自动路由）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
            ("target_id", False, "uint", "", ""),
        ),
    },
    "mark_private_msg_as_read": {
        "summary": "标记私聊消息已读",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
            ("user_id", False, "uint", "user_id", ""),
        ),
    },
    "modify_custom_face": {
        "summary": "修改收藏表情备注",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("emoji_id", True, "string", "", ""),
            ("desc", False, "string", "", ""),
        ),
    },
    "move_custom_face_to_front": {
        "summary": "收藏表情移到最前",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("emoji_id", True, "string", "", ""),
        ),
    },
    "move_group_file": {
        "summary": "移动群文件",
        "read_only": False,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("file_id", True, "string", "file_id", ""),
            ("parent_directory", True, "string", "", ""),
            ("target_directory", True, "string", "", ""),
        ),
    },
    "nc_get_packet_status": {
        "summary": "获取 packet 状态（占位）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "nc_get_user_status": {
        "summary": "获取用户在线/扩展状态",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
        ),
    },
    "ocr_image": {
        "summary": "OCR 图片（服务端，需图片 URL 或已缓存的图片 file_id）",
        "read_only": True,
        "category": "扩展",
        "aliases": (".ocr_image",),
        "params": (
            ("image", True, "string", "image", ""),
        ),
    },
    "rename_flash_file": {
        "summary": "重命名闪传文件",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("fileset_id", True, "string", "", ""),
            ("new_name", True, "string", "", ""),
        ),
    },
    "rename_group_file": {
        "summary": "重命名群文件",
        "read_only": False,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("file_id", True, "string", "file_id", ""),
            ("current_parent_directory", False, "string", "", ""),
            ("new_name", True, "string", "", ""),
        ),
    },
    "rename_group_file_folder": {
        "summary": "重命名群文件夹",
        "read_only": False,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("folder_id", True, "string", "", ""),
            ("new_folder_name", False, "string", "", ""),
            ("name", False, "string", "", ""),
        ),
    },
    "reply_qzone_public_feed": {
        "summary": "回复推荐动态的评论或其中某条回复",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("comment", True, "object", "", "详情或评论页返回的完整评论对象，保留 user 等原始字段"),
            ("content", True, "string | object[]", "", "非空文本，或非空上游 RichItem 对象数组；字符串始终原样发送，富文本请直接传对象数组，不是 OneBot 消息段"),
            ("reply", False, "object", "", "评论或回复页返回的完整回复对象，保留 user 等原始字段"),
        ),
    },
    "request_decrypt_key": {
        "summary": "请求数据库解密密钥",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("db_path", True, "string", "", ""),
        ),
    },
    "search_sys_faces": {
        "summary": "搜索 QQ 系统表情",
        "read_only": True,
        "category": "系统表情",
        "aliases": (),
        "params": (
            ("query", True, "string", "", "编号、名称、别名或分组名"),
        ),
    },
    "send_ark_share": {
        "summary": "分享用户/群 Ark 卡片（NapCat 标准名）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", False, "uint", "user_id", ""),
            ("group_id", False, "uint", "group_id", ""),
            ("phone_number", False, "string", "", ""),
        ),
    },
    "send_custom_face": {
        "summary": "发送账号收藏表情（emoji_id 或 MD5），保留表情显示样式",
        "read_only": False,
        "category": "消息",
        "aliases": (),
        "params": (
            ("emoji_id", True, "string", "", "当前账号收藏表情的完整 ID 或 32 位 MD5"),
            ("group_id", False, "uint", "group_id", "目标群号；与 user_id 二选一"),
            ("user_id", False, "uint", "user_id", "目标 QQ 号；与 group_id 二选一"),
            ("reply_to", False, "messageId", "message_id", "可选回复消息 ID"),
        ),
    },
    "send_flash_msg": {
        "summary": "发送闪传消息（私聊或群聊，引用 fileset_id 让对端下载）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("fileset_id", True, "string", "", ""),
            ("user_id", False, "uint", "user_id", ""),
            ("group_id", False, "uint", "group_id", ""),
        ),
    },
    "send_forward_msg": {
        "summary": "发送合并转发（按 message_type/群号自动路由）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("messages", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("message", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("message_type", False, "string", "", ""),
            ("group_id", False, "int", "", ""),
            ("user_id", False, "int", "", ""),
            ("source", False, "string", "", ""),
            ("summary", False, "string", "", ""),
            ("prompt", False, "string", "", ""),
            ("news", False, "raw", "", ""),
        ),
    },
    "send_group_ai_record": {
        "summary": "发送 AI 语音到群",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("character", True, "string", "", ""),
            ("text", True, "string", "", ""),
            ("chat_type", False, "int", "", ""),
        ),
    },
    "send_group_ark_share": {
        "summary": "分享群 Ark 卡片（NapCat 标准名）",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", ""),
        ),
    },
    "send_group_forward_msg": {
        "summary": "发送群合并转发",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("messages", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("message", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("source", False, "string", "", ""),
            ("summary", False, "string", "", ""),
            ("prompt", False, "string", "", ""),
            ("news", False, "raw", "", ""),
        ),
    },
    "send_group_msg": {
        "summary": "发送群消息",
        "read_only": False,
        "category": "消息",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("message", True, "message", "", ""),
            ("auto_escape", False, "bool", "", ""),
        ),
    },
    "send_like": {
        "summary": "点赞",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
            ("times", False, "int", "", ""),
        ),
    },
    "send_msg": {
        "summary": "发送消息（按 message_type/群号 自动路由群聊或私聊）",
        "read_only": False,
        "category": "消息",
        "aliases": (),
        "params": (
            ("message", True, "message", "", ""),
            ("message_type", False, "string", "", ""),
            ("group_id", False, "uint", "group_id", ""),
            ("user_id", False, "uint", "user_id", ""),
            ("auto_escape", False, "bool", "", ""),
        ),
    },
    "send_packet": {
        "summary": "发送原始 SSO 包（cmd + hex data）",
        "read_only": False,
        "category": "扩展",
        "aliases": (".send_packet",),
        "params": (
            ("cmd", True, "string", "", ""),
            ("data", False, "string", "", ""),
            ("rsp", False, "bool", "", ""),
        ),
    },
    "send_poke": {
        "summary": "拍一拍（群聊/私聊自动路由）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
            ("group_id", False, "uint", "group_id", ""),
        ),
    },
    "send_private_forward_msg": {
        "summary": "发送私聊合并转发",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
            ("messages", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("message", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("source", False, "string", "", ""),
            ("summary", False, "string", "", ""),
            ("prompt", False, "string", "", ""),
            ("news", False, "raw", "", ""),
        ),
    },
    "send_private_msg": {
        "summary": "发送私聊消息",
        "read_only": False,
        "category": "消息",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
            ("message", True, "message", "", ""),
            ("group_id", False, "int", "", ""),
            ("auto_escape", False, "bool", "", ""),
        ),
    },
    "send_qzone_msg": {
        "summary": "发表说说（QQ 空间，支持纯文字或带图；传 images 自动上传；可设置查看权限）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("content", True, "string", "", "说说正文"),
            ("images", False, "string[]", "", "图片数组（可选），支持 file:// http:// base64://；自动上传"),
            ("ugc_right", False, "int", "", "查看权限：1=所有人可见，4=好友可见，16=部分好友可见，64=仅自己可见，128=部分好友不可见"),
            ("target_uins", False, "uint[]", "", "权限作用 QQ 号数组；ugc_right=16 时表示可见名单，128 时表示不可见名单"),
        ),
    },
    "send_tuwen_ark": {
        "summary": "发送图文 Ark 卡片（私聊/群聊）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", False, "uint", "user_id", ""),
            ("group_id", False, "uint", "group_id", ""),
            ("title", True, "string", "", ""),
            ("desc", True, "string", "", ""),
            ("summary", False, "string", "", ""),
            ("preview_url", False, "string", "", ""),
            ("jump_url", True, "string", "", ""),
        ),
    },
    "set_diy_online_status": {
        "summary": "设置自定义在线状态",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("face_id", True, "int", "face_id", ""),
            ("face_type", False, "int", "", ""),
            ("wording", False, "string", "", ""),
        ),
    },
    "set_doubt_friends_add_request": {
        "summary": "处理可疑好友申请",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("flag", True, "string", "", ""),
            ("approve", False, "bool", "", ""),
        ),
    },
    "set_essence_msg": {
        "summary": "设置精华消息",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
        ),
    },
    "set_friend_add_request": {
        "summary": "处理好友添加请求",
        "read_only": False,
        "category": "请求",
        "aliases": (),
        "params": (
            ("flag", True, "string", "", ""),
            ("approve", False, "bool", "", ""),
        ),
    },
    "set_friend_remark": {
        "summary": "设置好友备注",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
            ("remark", True, "string", "", ""),
        ),
    },
    "set_friends_category": {
        "summary": "移动好友到指定分组",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("uin", True, "uint", "user_id", "要移动的好友 QQ 号"),
            ("categoryId", False, "int", "", "目标分组 ID"),
            ("categoryName", False, "string", "", "目标分组名称（必须唯一且完全匹配）"),
        ),
    },
    "set_group_add_option": {
        "summary": "设置加群选项",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("add_type", False, "int", "", ""),
            ("group_question", False, "string", "", ""),
            ("group_answer", False, "string", "", ""),
        ),
    },
    "set_group_add_request": {
        "summary": "处理加群请求",
        "read_only": False,
        "category": "请求",
        "aliases": (),
        "params": (
            ("flag", True, "string", "", ""),
            ("sub_type", False, "string", "", ""),
            ("type", False, "string", "", ""),
            ("approve", False, "bool", "", ""),
            ("reason", False, "string", "", ""),
        ),
    },
    "set_group_admin": {
        "summary": "设置/取消管理员",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
            ("enable", False, "bool", "", ""),
        ),
    },
    "set_group_admin_permissions": {
        "summary": "设置指定管理员的撤回和移除成员权限",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
            ("recall_member_message", False, "bool", "", ""),
            ("kick_member", False, "bool", "", ""),
            ("kick_member_per_day", False, "int", "", ""),
        ),
    },
    "set_group_admin_receive_verify": {
        "summary": "设置指定管理员是否接收加群验证消息",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
            ("enable", True, "bool", "", ""),
        ),
    },
    "set_group_album_media_like": {
        "summary": "",
        "read_only": False,
        "category": "群相册",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("album_id", True, "string", "", ""),
            ("batch_id", True, "string", "", ""),
            ("lloc", False, "string", "", ""),
        ),
    },
    "set_group_anonymous": {
        "summary": "匿名开关（未实现，返回 ok）",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
        ),
    },
    "set_group_anonymous_ban": {
        "summary": "匿名禁言（未实现，返回 ok）",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
        ),
    },
    "set_group_ban": {
        "summary": "禁言群成员（duration=0 解除）",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
            ("duration", False, "int", "duration", ""),
        ),
    },
    "set_group_card": {
        "summary": "设置群名片（空字符串清除）",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
            ("card", False, "string", "", ""),
        ),
    },
    "set_group_kick": {
        "summary": "踢出群成员",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
            ("reject_add_request", False, "bool", "", ""),
        ),
    },
    "set_group_kick_members": {
        "summary": "批量踢出群成员",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint[]", "", ""),
            ("reject_add_request", False, "bool", "", ""),
        ),
    },
    "set_group_leave": {
        "summary": "退群",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "set_group_member_invite_policy": {
        "summary": "设置群成员邀请策略",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("policy", True, "enum", "", ""),
        ),
    },
    "set_group_member_permissions": {
        "summary": "设置群成员权限（仅群主可改）",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("allow_member_upload_album", False, "bool", "", ""),
            ("allow_member_temporary_session", False, "bool", "", ""),
            ("allow_member_create_group", False, "bool", "", ""),
        ),
    },
    "set_group_name": {
        "summary": "设置群名",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("group_name", False, "string", "", ""),
        ),
    },
    "set_group_new_member_history_visibility": {
        "summary": "设置新成员是否可查看历史消息",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("visible", True, "bool", "", ""),
        ),
    },
    "set_group_portrait": {
        "summary": "设置群头像",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("file", True, "string", "image", ""),
        ),
    },
    "set_group_reaction": {
        "summary": "群聊表情回应",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", False, "uint", "group_id", ""),
            ("message_id", True, "messageId", "message_id", ""),
            ("code", True, "string", "", ""),
            ("is_set", False, "bool", "", ""),
        ),
    },
    "set_group_remark": {
        "summary": "设置群备注",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", ""),
            ("remark", True, "string", "", ""),
        ),
    },
    "set_group_robot_add_option": {
        "summary": "设置群机器人加群选项",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("robot_member_switch", False, "int", "", ""),
            ("robot_member_examine", False, "int", "", ""),
        ),
    },
    "set_group_search": {
        "summary": "设置群被搜索方式（群指纹 / 群号搜索开关）",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("no_finger_open", False, "int", "", ""),
            ("no_code_finger_open", False, "int", "", ""),
        ),
    },
    "set_group_sign": {
        "summary": "群签到",
        "read_only": False,
        "category": "扩展",
        "aliases": ("send_group_sign",),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
        ),
    },
    "set_group_special_title": {
        "summary": "设置群头衔",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("user_id", True, "uint", "member_id", "QQ 号"),
            ("special_title", False, "string", "", ""),
        ),
    },
    "set_group_todo": {
        "summary": "设置群待办",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("message_id", True, "messageId", "message_id", ""),
        ),
    },
    "set_group_whole_ban": {
        "summary": "全员禁言开关",
        "read_only": False,
        "category": "群管理",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("enable", False, "bool", "", ""),
        ),
    },
    "set_input_status": {
        "summary": "设置输入状态",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
            ("event_type", False, "int", "", ""),
        ),
    },
    "set_msg_emoji_like": {
        "summary": "设置消息表情回应",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("message_id", True, "messageId", "message_id", ""),
            ("emoji_id", True, "string", "", ""),
            ("set", False, "bool", "", ""),
        ),
    },
    "set_online_status": {
        "summary": "设置在线状态",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("status", True, "int", "", ""),
            ("ext_status", False, "int", "", ""),
            ("battery_status", False, "int", "", ""),
        ),
    },
    "set_qq_avatar": {
        "summary": "设置 QQ 头像",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("file", True, "string", "image", ""),
        ),
    },
    "set_qq_profile": {
        "summary": "设置 QQ 资料",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("nickname", False, "string", "", ""),
            ("personal_note", False, "string", "", ""),
            ("sex", False, "int", "", "0 未知，1 男，2 女"),
        ),
    },
    "set_qzone_ban": {
        "summary": "拉黑或解除拉黑某人（修改机器人自身 QQ 空间黑名单；enable=true 拉黑，false 解除）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", "目标 QQ 号"),
            ("enable", False, "bool", "", "true 拉黑，false 解除拉黑"),
        ),
    },
    "set_qzone_msg_right": {
        "summary": "修改一条已发说说的查看权限（QQ 空间，按 tid）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("tid", True, "string", "", "说说 tid（来自 get_qzone_msg_list / send_qzone_msg）"),
            ("ugc_right", True, "int", "", "查看权限：1=所有人可见，4=好友可见，16=部分好友可见，64=仅自己可见，128=部分好友不可见"),
            ("target_uins", False, "uint[]", "", "权限作用 QQ 号数组；ugc_right=16 时表示可见名单，128 时表示不可见名单"),
        ),
    },
    "set_qzone_profile": {
        "summary": "修改当前账号的 QQ 空间名称或说明",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("name", False, "string", "", "新的空间名称，空字符串表示清空，省略则保留"),
            ("description", False, "string", "", "新的空间说明，空字符串表示清空，省略则保留"),
        ),
    },
    "set_qzone_public_comment_like": {
        "summary": "点赞或取消赞推荐动态中的评论或回复",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("comment", True, "object", "", "详情或评论页返回的完整评论对象，保留 user 等原始字段"),
            ("enable", False, "bool", "", "true 点赞，false 取消赞"),
            ("reply", False, "object", "", "评论或回复页返回的完整回复对象，保留 user 等原始字段"),
        ),
    },
    "set_qzone_public_follow": {
        "summary": "蹲或取消蹲推荐动态作者",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("enable", False, "bool", "", "true 蹲，false 取消蹲"),
        ),
    },
    "set_qzone_public_like": {
        "summary": "点赞或取消赞推荐动态",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("enable", False, "bool", "", "true 点赞，false 取消赞"),
        ),
    },
    "set_qzone_public_upvote": {
        "summary": "推或取消推空友爱看动态（独立于普通赞）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("feed", True, "object", "", "get_qzone_public_feeds 返回的完整 feeds 条目，保留所有原始 cell 字段"),
            ("enable", False, "bool", "", "true 推，false 取消推"),
        ),
    },
    "set_restart": {
        "summary": "重启（不支持）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
        ),
    },
    "set_self_longnick": {
        "summary": "设置个性签名（longNick/long_nick，严格 string）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("longNick", False, "string", "", ""),
            ("long_nick", False, "string", "", ""),
        ),
    },
    "share_group_ex": {
        "summary": "分享群 Ark 卡片",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", ""),
        ),
    },
    "share_peer": {
        "summary": "分享用户/群 Ark 卡片",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("user_id", False, "uint", "user_id", ""),
            ("group_id", False, "uint", "group_id", ""),
            ("phone_number", False, "string", "", ""),
        ),
    },
    "test_download_stream": {
        "summary": "测试下载流(推送 10 个数据帧,验证流式传输,不触达 QQ)",
        "read_only": False,
        "category": "流式接口",
        "aliases": (),
        "params": (
            ("error", False, "bool", "", "是否触发测试错误"),
        ),
    },
    "trans_group_file": {
        "summary": "转存群文件",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", ""),
            ("file_id", True, "string", "file_id", ""),
        ),
    },
    "translate_en2zh": {
        "summary": "英译中",
        "read_only": True,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("words", True, "string[]", "", ""),
        ),
    },
    "unlike_qzone": {
        "summary": "取消对一条说说的点赞（QQ 空间；取消赞端点待真机核实）",
        "read_only": False,
        "category": "空间",
        "aliases": (),
        "params": (
            ("tid", True, "string", "", "说说 tid"),
            ("target_uin", False, "uint", "user_id", "说说所属 QQ 号，省略则为机器人自己"),
            ("abstime", False, "int", "timestamp", "说说发表时间（unix 秒），传真实值更可靠"),
        ),
    },
    "upload_file_stream": {
        "summary": "以流式分块方式上传文件到机器人本地(返回可用于发送的本地路径)",
        "read_only": False,
        "category": "流式接口",
        "aliases": (),
        "params": (
            ("stream_id", True, "string", "", "流 ID(客户端生成的 UUID,限 [A-Za-z0-9_-])"),
            ("chunk_data", False, "string", "", "分块数据(Base64)"),
            ("chunk_index", False, "int", "", "分块索引(从 0 开始)"),
            ("total_chunks", False, "int", "", "总分块数(新流必填)"),
            ("file_size", False, "int", "", "文件总大小(字节)"),
            ("expected_sha256", False, "string", "", "期望的整文件 SHA256(校验)"),
            ("is_complete", False, "bool", "", "是否为最后一个分块/触发合并"),
            ("filename", False, "string", "", "文件名"),
            ("reset", False, "bool", "", "重置并丢弃该流"),
            ("verify_only", False, "bool", "", "仅查询当前流状态"),
            ("file_retention", False, "int", "", "合并文件保留毫秒(0=不回收)"),
        ),
    },
    "upload_forward_msg": {
        "summary": "上传转发消息",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("messages", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("message", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("group_id", False, "uint", "group_id", ""),
        ),
    },
    "upload_foward_msg": {
        "summary": "上传转发消息（别名拼写）",
        "read_only": False,
        "category": "扩展",
        "aliases": (),
        "params": (
            ("messages", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("message", False, "message", "", "转发节点数组；节点 content 内的 reply.data.message 可提供自定义引用内容（字符串或消息段），qq/time/seq 可选；仅用于转发内引用预览。"),
            ("group_id", False, "uint", "group_id", ""),
        ),
    },
    "upload_group_file": {
        "summary": "上传群文件",
        "read_only": False,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("file", True, "string", "file", ""),
            ("name", False, "string", "", ""),
            ("folder", False, "string", "", ""),
            ("folder_id", False, "string", "", ""),
            ("upload_file", False, "bool", "", ""),
        ),
    },
    "upload_image_to_qun_album": {
        "summary": "",
        "read_only": False,
        "category": "群相册",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("album_id", True, "string", "", ""),
            ("album_name", True, "string", "", ""),
            ("file", True, "string", "image", ""),
        ),
    },
    "upload_private_file": {
        "summary": "上传私聊文件",
        "read_only": False,
        "category": "群文件",
        "aliases": (),
        "params": (
            ("user_id", True, "uint", "user_id", ""),
            ("file", True, "string", "file", ""),
            ("name", False, "string", "", ""),
            ("upload_file", False, "bool", "", ""),
        ),
    },
    "upload_video_to_qun_album": {
        "summary": "上传视频到群相册",
        "read_only": False,
        "category": "群相册",
        "aliases": (),
        "params": (
            ("group_id", True, "uint", "group_id", "群号"),
            ("album_id", True, "string", "", "相册 id"),
            ("album_name", True, "string", "", "相册名称"),
            ("file", True, "string", "video", "视频文件"),
        ),
    },
}
