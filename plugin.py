"""
2026-06-04 try1 初次构建
2026-06-05 try2 修改为只按白名单流转模式，取消黑名单
"""

from maibot_sdk import API, Field, MaiBotPlugin, MessageGateway, PluginConfigBase, PluginContext, Tool, Command, EventHandler, HookHandler
from maibot_sdk.types import EventType, ToolParameterInfo, ToolParamType, HookMode, HookOrder, ErrorPolicy
from typing import Dict, Optional, ClassVar, List, Any
import asyncio
import time
import datetime

# ============================================================================
# 多语言化
# ============================================================================
def _schema_i18n(
    *,
    label_en: str,
    label_ja: str,
    hint_en: Optional[str] = None,
    hint_ja: Optional[str] = None,
    placeholder_en: Optional[str] = None,
    placeholder_ja: Optional[str] = None,
) -> Dict[str, Dict[str, str]]:
    """构造 WebUI 配置项多语言说明，保留外层中文字段兼容旧格式。"""
    i18n: Dict[str, Dict[str, str]] = {
        "en_US": {"label": label_en},
        "ja_JP": {"label": label_ja},
    }
    if hint_en is not None:
        i18n["en_US"]["hint"] = hint_en
    if hint_ja is not None:
        i18n["ja_JP"]["hint"] = hint_ja
    if placeholder_en is not None:
        i18n["en_US"]["placeholder"] = placeholder_en
    if placeholder_ja is not None:
        i18n["ja_JP"]["placeholder"] = placeholder_ja
    return i18n

# ============================================================================
# WebUI插件控件生成
# ============================================================================
class BasicConfig(PluginConfigBase):
    """基础设置。"""
    
    __ui_label__: ClassVar[str] = "基础设置"
    __ui_order__: ClassVar[int] = 0
    
    enabled: bool = Field(
        default=False,
        description="是否启用聊天流转插件",
        json_schema_extra={
            "label": "插件开关",
            "i18n": _schema_i18n(
                label_en="Enable",
                label_ja="プラグインを有効化",
            ),
            "order": 0,
        },
    )


class WhitelistStreamsConfig(PluginConfigBase):
    """聊天流白名单设置。只有白名单中的聊天流才会参与消息流转。"""
    
    __ui_label__: ClassVar[str] = "聊天流白名单"
    __ui_order__: ClassVar[int] = 1
    
    whitelist_streams: List[str] = Field(
        default_factory=list,
        description="白名单聊天流ID列表，只有这些聊天流中的消息会被转发，且只会转发到这些聊天流",
        json_schema_extra={
            "label": "白名单聊天流",
            "hint": "只有白名单中的聊天流才会参与流转（来源和目标都必须是白名单中的聊天流）",
            "i18n": _schema_i18n(
                label_en="Whitelist streams",
                label_ja="ホワイトリストストリーム",
                hint_en="Only whitelisted chat streams will participate in message flow (both source and target must be in whitelist)",
                hint_ja="ホワイトリストに登録されたチャットストリームのみがメッセージフローに参加します（ソースとターゲットの両方がホワイトリストにある必要があります）",
                placeholder_en="Enter stream ID",
                placeholder_ja="ストリームIDを入力",
            ),
            "order": 0,
        },
    )


class UserWhitelistConfig(PluginConfigBase):
    """用户白名单设置。"""
    
    __ui_label__: ClassVar[str] = "用户白名单"
    __ui_order__: ClassVar[int] = 2
    
    user_whitelist_enabled: bool = Field(
        default=False,
        description="是否启用用户白名单",
        json_schema_extra={
            "label": "启用用户白名单",
            "hint": "启用后，白名单中的用户消息不会被转发",
            "i18n": _schema_i18n(
                label_en="Enable user whitelist",
                label_ja="ユーザーホワイトリストを有効化",
                hint_en="When enabled, messages from whitelisted users will not be forwarded",
                hint_ja="有効にすると、ホワイトリストに登録されたユーザーのメッセージは転送されません",
            ),
            "order": 0,
        },
    )
    
    whitelist_users: List[str] = Field(
        default_factory=list,
        description="用户白名单列表",
        json_schema_extra={
            "label": "白名单用户",
            "hint": "这些用户的消息不会被转发",
            "i18n": _schema_i18n(
                label_en="Whitelist users",
                label_ja="ホワイトリストユーザー",
                hint_en="Messages from these users will not be forwarded",
                hint_ja="これらのユーザーからのメッセージは転送されません",
                placeholder_en="Enter user ID",
                placeholder_ja="ユーザーIDを入力",
            ),
            "order": 1,
        },
    )


class KeywordFilterConfig(PluginConfigBase):
    """关键词过滤设置。"""
    
    __ui_label__: ClassVar[str] = "关键词过滤"
    __ui_order__: ClassVar[int] = 3
    
    keyword_filter_enabled: bool = Field(
        default=False,
        description="是否启用关键词过滤",
        json_schema_extra={
            "label": "启用关键词过滤",
            "hint": "启用后，包含指定关键词的消息不会被转发",
            "i18n": _schema_i18n(
                label_en="Enable keyword filter",
                label_ja="キーワードフィルターを有効化",
                hint_en="When enabled, messages containing specified keywords will not be forwarded",
                hint_ja="有効にすると、指定されたキーワードを含むメッセージは転送されません",
            ),
            "order": 0,
        },
    )
    
    filtered_keywords: List[str] = Field(
        default_factory=list,
        description="过滤关键词列表",
        json_schema_extra={
            "label": "过滤关键词",
            "hint": "包含这些关键词的消息不会被转发",
            "i18n": _schema_i18n(
                label_en="Filtered keywords",
                label_ja="フィルターキーワード",
                hint_en="Messages containing these keywords will not be forwarded",
                hint_ja="これらのキーワードを含むメッセージは転送されません",
                placeholder_en="Enter keyword",
                placeholder_ja="キーワードを入力",
            ),
            "order": 1,
        },
    )


class ReplyConfig(PluginConfigBase):
    """回复消息设置。"""
    
    __ui_label__: ClassVar[str] = "回复消息设置"
    __ui_order__: ClassVar[int] = 4
    
    forward_reply: bool = Field(
        default=True,
        description="是否转发回复消息",
        json_schema_extra={
            "label": "转发回复消息",
            "hint": "是否转发回复类型的消息",
            "i18n": _schema_i18n(
                label_en="Forward reply messages",
                label_ja="返信メッセージを転送",
                hint_en="Whether to forward reply-type messages",
                hint_ja="返信タイプのメッセージを転送するかどうか",
            ),
            "order": 0,
        },
    )


class WatchYourStreamConfig(PluginConfigBase):
    """配置大纲"""
    basic: BasicConfig = Field(default_factory=BasicConfig)
    whitelist_streams: WhitelistStreamsConfig = Field(default_factory=WhitelistStreamsConfig)
    user_whitelist: UserWhitelistConfig = Field(default_factory=UserWhitelistConfig)
    keyword_filter: KeywordFilterConfig = Field(default_factory=KeywordFilterConfig)
    reply: ReplyConfig = Field(default_factory=ReplyConfig)


# ============================================================================
# 插件主体
# ============================================================================
class WatchYourStreamPlugin(MaiBotPlugin):
    """聊天流转插件主类"""
    
    async def on_load(self) -> None:
        """插件加载时的回调"""
        # 初始化内部状态
        # 加载配置
        # 初始化流转队列
        # 记录日志
        pass
    
    async def on_unload(self) -> None:
        """插件卸载时的回调"""
        # 清理资源
        # 保存状态
        # 记录日志
        pass
    
    async def on_config_update(self, scope: str, config_data: dict, version: str) -> None:
        """配置更新时的回调"""
        # 当 scope == "self" 时，self.config 已自动更新
        # 重新加载配置
        # 记录日志
        pass
    
    # ========================================================================
    # EventHandler 方法
    # ========================================================================
    
    @EventHandler(
        "on_message_handler",
        description="处理收到的消息并进行流转",
        event_type=EventType.ON_MESSAGE,
    )
    async def on_message_received(self, message: dict, **kwargs) -> dict:
        """
        消息接收事件处理器
        
        功能：
        1. 检查插件是否启用
        2. 获取消息的聊天流ID和用户ID
        3. 检查消息来源是否在聊天流白名单中
        4. 检查用户是否在用户白名单中
        5. 检查消息是否包含过滤关键词
        6. 检查是否为回复消息（根据配置决定是否转发）
        7. 将符合条件的消息转发到白名单中的其他聊天流（排除来源）
        """
        pass
    
    # ========================================================================
    # Command 方法
    # ========================================================================
    
    @Command("watch_status", description="查看聊天流转状态", pattern=r"^/watch_status$")
    async def handle_watch_status(self, **kwargs):
        """
        查看聊天流转插件状态
        
        功能：
        1. 获取当前配置状态
        2. 返回聊天流白名单列表
        3. 返回用户白名单/关键词过滤状态
        4. 记录日志
        """
        pass
    
    @Command("watch_test", description="测试聊天流转", pattern=r"^/watch_test$")
    async def handle_watch_test(self, **kwargs):
        """
        测试聊天流转
        
        功能：
        1. 获取当前聊天流ID
        2. 发送测试消息到白名单中的其他聊天流
        3. 记录日志
        """
        pass
    
    # ========================================================================
    # Tool 方法
    # ========================================================================
    
    @Tool(
        "get_whitelist_streams",
        brief_description="获取聊天流白名单列表",
        detailed_description="返回当前配置中允许参与流转的聊天流ID列表（白名单）",
    )
    async def tool_get_whitelist_streams(self, **kwargs) -> dict:
        """
        获取聊天流白名单列表
        
        返回：
        - success: 是否成功
        - streams: 白名单聊天流ID列表
        - count: 聊天流数量
        """
        pass
    
    @Tool(
        "check_user_in_whitelist",
        brief_description="检查用户是否在用户白名单中",
        detailed_description="根据用户ID判断该用户是否在用户白名单中",
        parameters=[
            ToolParameterInfo(
                name="user_id",
                param_type=ToolParamType.STRING,
                description="用户ID",
                required=True,
            ),
        ],
    )
    async def tool_check_user_whitelist(self, user_id: str, **kwargs) -> dict:
        """
        检查用户是否在用户白名单中
        
        参数：
        - user_id: 用户ID
        
        返回：
        - in_whitelist: 是否在白名单中
        - user_whitelist_enabled: 用户白名单是否启用
        """
        pass
    
    @Tool(
        "check_keywords_in_message",
        brief_description="检查消息是否包含过滤关键词",
        detailed_description="检查消息文本中是否包含配置的过滤关键词",
        parameters=[
            ToolParameterInfo(
                name="message_text",
                param_type=ToolParamType.STRING,
                description="消息文本内容",
                required=True,
            ),
        ],
    )
    async def tool_check_keywords(self, message_text: str, **kwargs) -> dict:
        """
        检查消息是否包含过滤关键词
        
        参数：
        - message_text: 消息文本内容
        
        返回：
        - contains_keywords: 是否包含关键词
        - matched_keywords: 匹配到的关键词列表
        - keyword_filter_enabled: 关键词过滤是否启用
        """
        pass
    
    @Tool(
        "get_stream_info",
        brief_description="获取聊天流信息",
        detailed_description="根据聊天流ID获取该聊天流的详细信息",
        parameters=[
            ToolParameterInfo(
                name="stream_id",
                param_type=ToolParamType.STRING,
                description="聊天流ID",
                required=True,
            ),
        ],
    )
    async def tool_get_stream_info(self, stream_id: str, **kwargs) -> dict:
        """
        获取聊天流信息
        
        参数：
        - stream_id: 聊天流ID
        
        返回：
        - success: 是否成功
        - stream_info: 聊天流详细信息（平台、类型、名称等）
        """
        pass
    
    @Tool(
        "forward_message_to_streams",
        brief_description="转发消息到指定聊天流",
        detailed_description="将消息内容转发到指定的聊天流（目标必须在白名单中）",
        parameters=[
            ToolParameterInfo(
                name="target_stream_id",
                param_type=ToolParamType.STRING,
                description="目标聊天流ID",
                required=True,
            ),
            ToolParameterInfo(
                name="message_content",
                param_type=ToolParamType.STRING,
                description="要转发的消息内容",
                required=True,
            ),
            ToolParameterInfo(
                name="source_info",
                param_type=ToolParamType.STRING,
                description="来源信息（可选）",
                required=False,
            ),
        ],
    )
    async def tool_forward_message_to_streams(
        self,
        target_stream_id: str,
        message_content: str,
        source_info: str = "",
        **kwargs
    ) -> dict:
        """
        转发消息到指定聊天流
        
        参数：
        - target_stream_id: 目标聊天流ID
        - message_content: 要转发的消息内容
        - source_info: 来源信息（可选）
        
        返回：
        - success: 是否成功
        - message: 结果消息
        """
        pass
    
    # ========================================================================
    # HookHandler 方法
    # ========================================================================
    
    @HookHandler(
        "chat.receive.before_process",
        name="message_flow_interceptor",
        description="消息流转拦截器，在消息处理前决定是否拦截",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
        error_policy=ErrorPolicy.SKIP,
    )
    async def hook_before_process(self, **kwargs) -> dict:
        """
        消息处理前的拦截钩子
        
        功能：
        1. 检查插件是否启用
        2. 判断当前消息是否需要流转处理（来源是否在白名单中）
        3. 可选：阻止消息继续处理（根据配置）
        
        返回：
        - action: "continue" 或 "abort"
        - modified_kwargs: 修改后的参数
        """
        pass
    
    @HookHandler(
        "send_service.before_send",
        name="forward_send_interceptor",
        description="转发消息发送拦截器",
        mode=HookMode.BLOCKING,
        order=HookOrder.NORMAL,
        error_policy=ErrorPolicy.SKIP,
    )
    async def hook_before_send(self, **kwargs) -> dict:
        """
        发送消息前的拦截钩子
        
        功能：
        1. 检查当前发送是否为转发消息
        2. 记录转发日志
        3. 可选：修改发送参数
        
        返回：
        - action: "continue" 或 "abort"
        - modified_kwargs: 修改后的参数
        """
        pass
    
    @HookHandler(
        "chat.command.after_execute",
        name="command_logger",
        description="命令执行后记录日志",
        mode=HookMode.OBSERVE,
        order=HookOrder.LATE,
    )
    async def hook_after_command(self, **kwargs) -> None:
        """
        命令执行后的观察钩子
        
        功能：
        1. 记录命令执行日志
        2. 统计命令使用情况
        """
        pass


def create_plugin():
    """创建插件实例"""
    return WatchYourStreamPlugin()


# try
#####构建过程详见NOREADME.md#####