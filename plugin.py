"""
2026-06-04 try1
2026-06-05 try2
2026-06-05 try3
2026-06-05 try4
2026-06-05 try5 
1.使 WebUI 的多语言配置能够正确生效。
2.增加流转日志 [消息流转]：在 _perform_flow 方法中，成功发送回复后添加如下日志：
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
    __ui_label__: ClassVar[str] = "基础设置"
    __ui_order__: ClassVar[int] = 0
    enabled: bool = Field(default=False, description="是否启用聊天流转插件",
        json_schema_extra={"label": "插件开关", "order": 0})
    config_version: str = Field(default="1.0.0", description="配置版本",
        json_schema_extra={"label": "配置版本", "order": 1})

class WhitelistStreamsConfig(PluginConfigBase):
    __ui_label__: ClassVar[str] = "聊天流白名单"
    __ui_order__: ClassVar[int] = 1
    whitelist_streams: List[str] = Field(default_factory=list,
        description="白名单聊天流ID列表，只有这些流参与流转",
        json_schema_extra={"label": "白名单聊天流", "placeholder": "输入流ID", "order": 0})

class UserWhitelistConfig(PluginConfigBase):
    __ui_label__: ClassVar[str] = "用户白名单"
    __ui_order__: ClassVar[int] = 2
    user_whitelist_enabled: bool = Field(default=False, description="启用用户白名单",
        json_schema_extra={"label": "启用用户白名单", "order": 0})
    whitelist_users: List[str] = Field(default_factory=list,
        description="这些用户的消息不会触发流转",
        json_schema_extra={"label": "白名单用户", "placeholder": "输入用户ID", "order": 1})

class KeywordFilterConfig(PluginConfigBase):
    __ui_label__: ClassVar[str] = "关键词过滤"
    __ui_order__: ClassVar[int] = 3
    keyword_filter_enabled: bool = Field(default=False, description="启用关键词过滤",
        json_schema_extra={"label": "启用关键词过滤", "order": 0})
    filtered_keywords: List[str] = Field(default_factory=list,
        description="包含这些关键词的消息不触发流转",
        json_schema_extra={"label": "过滤关键词", "placeholder": "输入关键词", "order": 1})

class LLMSettingsConfig(PluginConfigBase):
    __ui_label__: ClassVar[str] = "LLM与历史设置"
    __ui_order__: ClassVar[int] = 4
    enabled: bool = Field(default=True, description="启用LLM生成回复",
        json_schema_extra={"label": "启用LLM", "order": 0})
    history_limit: int = Field(default=20, ge=1, le=100, description="获取最近消息数量",
        json_schema_extra={"label": "历史消息数量", "order": 1})
    include_forwarded_messages: bool = Field(default=False,
        description="是否包含已经被流转的消息",
        json_schema_extra={"label": "包含流转消息", "order": 2})
    llm_prompt: str = Field(default="基于以下对话历史...", description="LLM提示词",
        json_schema_extra={"label": "LLM提示词", "widget": "textarea", "order": 3})

class TriggerConfig(PluginConfigBase):
    __ui_label__: ClassVar[str] = "触发条件"
    __ui_order__: ClassVar[int] = 5
    require_same_user_recent: bool = Field(default=True,
        description="要求目标流中最近有相同用户发言",
        json_schema_extra={"label": "要求相同用户近期发言", "order": 0})
    same_user_recent_limit: int = Field(default=10, ge=1, le=50,
        description="检查最近多少条消息中存在相同用户",
        json_schema_extra={"label": "检查消息数", "order": 1})
    same_user_recent_time_window: int = Field(default=300, ge=0,
        description="时间窗口（秒），0表示不限",
        json_schema_extra={"label": "时间窗口(秒)", "order": 2})
    action_cooldown_seconds: int = Field(default=60, ge=5,
        description="每个流的动作冷却时间（秒），持久化存储，重启不丢失",
        json_schema_extra={"label": "冷却时间(秒)", "order": 3})

class ReplyConfig(PluginConfigBase):
    __ui_label__: ClassVar[str] = "回复设置"
    __ui_order__: ClassVar[int] = 6
    forward_reply: bool = Field(default=True, description="是否转发回复消息作为上下文",
        json_schema_extra={"label": "包含回复消息", "order": 0})

class WatchYourStreamConfig(PluginConfigBase):
    basic: BasicConfig = Field(default_factory=BasicConfig)
    whitelist_streams: WhitelistStreamsConfig = Field(default_factory=WhitelistStreamsConfig)
    user_whitelist: UserWhitelistConfig = Field(default_factory=UserWhitelistConfig)
    keyword_filter: KeywordFilterConfig = Field(default_factory=KeywordFilterConfig)
    llm_settings: LLMSettingsConfig = Field(default_factory=LLMSettingsConfig)
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    reply: ReplyConfig = Field(default_factory=ReplyConfig)


# ============================================================================
# 插件主体
# ============================================================================
class WatchYourStreamPlugin(MaiBotPlugin):
    """跨群话题流转插件 - 自动将同一用户的发言在多个群聊间延续话题（持久化冷却）"""
    
    config_model = WatchYourStreamConfig  # 使多语言配置生效
    
    def __init__(self):
        super().__init__()
        self._processing: Dict[str, bool] = {}     # 内存锁，防止同一流并发处理
    
    async def on_load(self) -> None:
        self.ctx.logger.info("[聊天流转] 插件加载 (try5 - 持久化冷却 + 流转日志)")
        self._processing.clear()
    
    async def on_unload(self) -> None:
        self.ctx.logger.info("[聊天流转] 插件卸载")
    
    async def on_config_update(self, scope: str, config_data: dict, version: str) -> None:
        if scope == "self":
            self.ctx.logger.info("[聊天流转] 配置已更新")
    
    # ------------------------------------------------------------------------
    # 冷却持久化操作
    # ------------------------------------------------------------------------
    async def _get_last_trigger_time(self, stream_id: str) -> float:
        """从数据库获取该流的上次触发时间戳，如果没有则返回0"""
        try:
            result = await self.ctx.db.get(
                model_name="WatchYourStreamCooldown",
                filters={"stream_id": stream_id},
                single_result=True
            )
            if result and "last_trigger_time" in result:
                return float(result["last_trigger_time"])
            return 0.0
        except Exception as e:
            self.ctx.logger.error(f"[聊天流转] 获取冷却记录失败 {stream_id}: {e}")
            return 0.0
    
    async def _set_last_trigger_time(self, stream_id: str, timestamp: float) -> bool:
        """保存该流的上次触发时间到数据库"""
        try:
            await self.ctx.db.save(
                model_name="WatchYourStreamCooldown",
                data={"stream_id": stream_id, "last_trigger_time": timestamp},
                key_field="stream_id",
                key_value=stream_id
            )
            return True
        except Exception as e:
            self.ctx.logger.error(f"[聊天流转] 保存冷却记录失败 {stream_id}: {e}")
            return False
    
    async def _is_cooldown_active(self, stream_id: str) -> bool:
        """检查冷却是否生效（基于持久化时间）"""
        last_time = await self._get_last_trigger_time(stream_id)
        if last_time == 0:
            return False
        cooldown = self.config.trigger.action_cooldown_seconds
        elapsed = time.time() - last_time
        return elapsed < cooldown
    
    async def _update_cooldown(self, stream_id: str):
        """触发后更新冷却时间"""
        await self._set_last_trigger_time(stream_id, time.time())
    
    # ------------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------------
    async def _check_user_in_recent_messages(self, stream_id: str, user_id: str) -> bool:
        cfg = self.config.trigger
        limit = cfg.same_user_recent_limit
        time_window = cfg.same_user_recent_time_window
        
        try:
            messages = await self.ctx.message.get_recent(stream_id, limit=limit)
            if not messages:
                return False
            
            now = time.time()
            for msg in messages:
                msg_ts = msg.get("timestamp", 0)
                if time_window > 0 and (now - msg_ts) > time_window:
                    continue
                msg_user = msg.get("user_info", {}).get("user_id", "")
                if msg_user == user_id:
                    return True
            return False
        except Exception as e:
            self.ctx.logger.error(f"[聊天流转] 检查最近消息失败 {stream_id}: {e}")
            return False
    
    async def _build_history_context(self, stream_id: str, current_message: str, source_user: str) -> str:
        cfg = self.config.llm_settings
        limit = cfg.history_limit
        try:
            messages = await self.ctx.message.get_recent(stream_id, limit=limit)
            if not messages:
                return "（无历史消息）"
            
            lines = []
            for msg in reversed(messages):
                if not cfg.include_forwarded_messages:
                    pass
                user_info = msg.get("user_info", {})
                user_name = user_info.get("nickname") or user_info.get("user_name") or user_info.get("user_id", "未知")
                content = msg.get("raw_message", "") or msg.get("content", "")
                lines.append(f"[{user_name}]: {content}")
            
            history_text = "\n".join(lines)
            return history_text if history_text else "（无历史消息）"
        except Exception as e:
            self.ctx.logger.error(f"[聊天流转] 构建历史上下文失败: {e}")
            return "（获取历史失败）"
    
    async def _generate_reply(self, history: str, current_message: str, source_user: str) -> Optional[str]:
        cfg = self.config.llm_settings
        if not cfg.enabled:
            return None
        prompt = cfg.llm_prompt.format(
            history=history,
            current_message=current_message,
            source_user=source_user
        )
        try:
            result = await self.ctx.llm.generate(prompt=prompt, temperature=0.7, max_tokens=150)
            if result.get("success"):
                reply = result.get("response", "").strip()
                if reply:
                    return reply
            return None
        except Exception as e:
            self.ctx.logger.error(f"[聊天流转] LLM生成失败: {e}")
            return None
    
    async def _should_trigger_for_stream(self, target_stream: str, source_user: str, current_message: str) -> bool:
        if await self._is_cooldown_active(target_stream):
            self.ctx.logger.debug(f"[聊天流转] 目标流 {target_stream} 处于冷却中，跳过")
            return False
        if self.config.trigger.require_same_user_recent:
            if not await self._check_user_in_recent_messages(target_stream, source_user):
                self.ctx.logger.debug(f"[聊天流转] 目标流 {target_stream} 近期无相同用户发言，跳过")
            return False
        return True
    
    async def _perform_flow(self, target_stream: str, source_stream: str, source_user: str, current_message: str):
        """执行流转：获取上下文，生成回复，发送，并更新持久化冷却"""
        if self._processing.get(target_stream, False):
            self.ctx.logger.debug(f"[聊天流转] 目标流 {target_stream} 正在处理中，跳过")
            return
        self._processing[target_stream] = True
        try:
            if await self._is_cooldown_active(target_stream):
                return
            
            history = await self._build_history_context(target_stream, current_message, source_user)
            reply = await self._generate_reply(history, current_message, source_user)
            if not reply:
                self.ctx.logger.info(f"[聊天流转] 目标流 {target_stream} LLM未生成回复")
                return
            
            await self.ctx.send.text(reply, target_stream)
            
            # 记录流转成功日志（格式：消息流转 + 详情）
            self.ctx.logger.info(f"[消息流转] 消息已流转！来源流: {source_stream} -> 目标流: {target_stream}, 回复内容: {reply[:50]}")
            
            await self._update_cooldown(target_stream)
        except Exception as e:
            self.ctx.logger.error(f"[聊天流转] 流转失败 {target_stream}: {e}")
        finally:
            self._processing[target_stream] = False
    
    # ========================================================================
    # EventHandler 核心处理
    # ========================================================================
    @EventHandler(
        "on_message_handler",
        description="处理消息并触发跨群流转",
        event_type=EventType.ON_MESSAGE,
        intercept_message=False,
        weight=10,
    )
    async def on_message_received(self, message: dict, **kwargs) -> dict:
        if not self.config.basic.enabled:
            return {"intercepted": False}
        
        stream_id = message.get("stream_id", "")
        if not stream_id:
            return {"intercepted": False}
        user_info = message.get("user_info", {})
        user_id = user_info.get("user_id", "")
        if not user_id:
            return {"intercepted": False}
        raw_message = message.get("raw_message", "") or message.get("content", "")
        if not raw_message:
            return {"intercepted": False}
        
        if self.config.user_whitelist.user_whitelist_enabled:
            if user_id in self.config.user_whitelist.whitelist_users:
                self.ctx.logger.debug(f"[聊天流转] 用户 {user_id} 在白名单中，跳过")
                return {"intercepted": False}
        
        if self.config.keyword_filter.keyword_filter_enabled:
            keywords = self.config.keyword_filter.filtered_keywords
            if any(kw in raw_message for kw in keywords):
                self.ctx.logger.debug(f"[聊天流转] 消息包含过滤关键词，跳过")
                return {"intercepted": False}
        
        whitelist = self.config.whitelist_streams.whitelist_streams
        if not whitelist:
            return {"intercepted": False}
        
        if stream_id not in whitelist:
            return {"intercepted": False}
        
        tasks = []
        for target in whitelist:
            if target == stream_id:
                continue
            if await self._should_trigger_for_stream(target, user_id, raw_message):
                tasks.append(self._perform_flow(target, stream_id, user_id, raw_message))
        
        if tasks:
            asyncio.gather(*tasks)
        
        return {"intercepted": False}
    
    # ========================================================================
    # Command 命令
    # ========================================================================
    @Command("watch_status", description="查看聊天流转状态", pattern=r"^/watch_status$")
    async def handle_status(self, **kwargs):
        stream_id = kwargs.get("stream_id", "")
        cfg = self.config
        status_lines = [
            f"插件状态: {'启用' if cfg.basic.enabled else '禁用'}",
            f"白名单流: {len(cfg.whitelist_streams.whitelist_streams)} 个",
            f"用户白名单: {'启用' if cfg.user_whitelist.user_whitelist_enabled else '禁用'}",
            f"关键词过滤: {'启用' if cfg.keyword_filter.keyword_filter_enabled else '禁用'}",
            f"LLM生成: {'启用' if cfg.llm_settings.enabled else '禁用'}",
            f"历史消息数: {cfg.llm_settings.history_limit}",
            f"冷却时间: {cfg.trigger.action_cooldown_seconds}秒 (持久化存储，重启不丢失)",
        ]
        await self.ctx.send.text("\n".join(status_lines), stream_id)
        return True, "状态已发送", 1
    
    @Command("watch_test", description="测试聊天流转", pattern=r"^/watch_test$")
    async def handle_test(self, **kwargs):
        stream_id = kwargs.get("stream_id", "")
        await self.ctx.send.text("[聊天流转] 测试消息：如果你在多个群聊中说话，我会尝试帮你延续话题。冷却记录会持久保存。", stream_id)
        self.ctx.logger.info(f"[聊天流转] 测试命令触发于 {stream_id}")
        return True, "测试消息已发送", 1


def create_plugin():
    return WatchYourStreamPlugin()


# try5
#####构建过程详见NOREADME.md#####