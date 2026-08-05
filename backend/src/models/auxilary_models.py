import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints
MAX_HISTORY_MESSAGES = 10
MAX_PROMPT_LENGTH = 20000
DEFAULT_HANDOFF_KEYWORDS = "оператор, менеджер, человек, manager, human"


BusinessType = Literal["confectionery", "flower_shop", "cafe_restaurant", "other"]


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=128)
    business_type: BusinessType = "other"


class ChannelCreate(BaseModel):
    tenant_id: uuid.UUID
    platform: Literal["instagram", "whatsapp"] = "instagram"
    external_account_id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=255)


class BotSettingsUpdate(BaseModel):
    enabled: bool = True
    handoff_keywords: str = Field(default=DEFAULT_HANDOFF_KEYWORDS, max_length=500)
    system_prompt: str | None = Field(default=None, max_length=MAX_PROMPT_LENGTH)


NormalizedPrompt = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_PROMPT_LENGTH),
]
NormalizedOptionalTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=255),
] | None


class AdminBotPromptUpdate(BaseModel):
    system_prompt: NormalizedPrompt
    title: NormalizedOptionalTitle = None


class AdminBotPromptResponse(BaseModel):
    tenant_id: str
    company_name: str
    username: str | None = None
    title: str
    system_prompt: str
    version: int


class CommentPromptUpdate(BaseModel):
    system_prompt: NormalizedPrompt
    title: NormalizedOptionalTitle = None


class CommentPromptResponse(BaseModel):
    tenant_id: str
    title: str
    system_prompt: str
    version: int


class IntentPromptUpdate(BaseModel):
    system_prompt: NormalizedPrompt
    title: NormalizedOptionalTitle = None


class IntentPromptResponse(BaseModel):
    tenant_id: str
    company_name: str
    username: str | None = None
    title: str
    system_prompt: str
    version: int


class InstagramBotStatusUpdate(BaseModel):
    enabled: bool


class KnowledgeTextCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=10000)
    source_url: str | None = Field(default=None, max_length=2000)
    quantity_available: int | None = Field(default=None, ge=0)


class KnowledgeEntryResponse(BaseModel):
    id: str
    company_id: str
    entry_type: Literal["text", "product_photo"]
    title: str
    content: str
    source_url: str | None = None
    image_url: str | None = None
    image_mime_type: str | None = None
    quantity_available: int | None = None
    created_at: datetime
    updated_at: datetime


class InstagramIntegrationResponse(BaseModel):
    tenant_id: str
    ig_activated: bool
    wp_activated: bool
    ig_enabled: bool
    wp_enabled: bool
    user_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    account_type: str | None = None
    profile_picture_url: str | None = None

class InstagramConnectUrlResponse(BaseModel):
    auth_url: str


class SimulateWebhookIn(BaseModel):
    platform: Literal["instagram", "whatsapp"] = "instagram"
    account_id: str = Field(min_length=1, max_length=128)
    conversation_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=512)
    sender_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4000)


class SimulateWebhookResponse(BaseModel):
    status: Literal["accepted"]
    tenant_id: str
    conversation_id: str
    inbound_message_id: str
    outbound_message_id: str


class WhatsAppMessageIn(BaseModel):
    message_id: str = Field(min_length=1, max_length=512)
    chat_id: str = Field(min_length=1, max_length=255)
    sender_id: str = Field(min_length=1, max_length=255)
    recipient_id: str = Field(min_length=1, max_length=255)
    from_me: bool = False
    body: str = Field(default="", max_length=10000)
    message_type: str | None = Field(default=None, max_length=64)
    has_media: bool = False
    timestamp: int | None = None
    customer_name: str | None = Field(default=None, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=64)
    payload: dict = Field(default_factory=dict)


class WhatsAppMessageResponse(BaseModel):
    status: Literal["accepted", "rejected"]
    tenant_id: str
    conversation_id: str
    message_id: str


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    business_type: BusinessType = "other"
    business_type_label: str = "Digər biznes"
    is_active: bool = True
    package_code: Literal["basic", "full"] = "basic"
    access_locked: bool = False


class CompanySubscriptionUpdate(BaseModel):
    package_code: Literal["basic", "full"]
    access_locked: bool = False
    locked_reason: str | None = Field(default=None, max_length=1000)


class CompanySubscriptionResponse(BaseModel):
    company_id: str
    package_code: Literal["basic", "full"]
    monthly_text_messages_limit: int | None = None
    monthly_voice_messages_limit: int | None = None
    autoposting_enabled: bool
    access_locked: bool
    locked_reason: str | None = None
    locked_at: datetime | None = None
    usage_period: str
    text_messages_used: int
    voice_messages_used: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChannelResponse(BaseModel):
    id: str
    tenant_id: str
    platform: Literal["instagram", "whatsapp"]
    external_account_id: str
    display_name: str

class BotSettingsResponse(BaseModel):
    tenant_id: str
    system_prompt: str
    handoff_keywords: str


class AutomationSettingsUpdate(BaseModel):
    client_reminder_enabled: bool = False
    client_reminder_delay_minutes: int = Field(default=120, ge=15, le=1440)
    client_reminder_message: str = Field(default="", max_length=1000)
    autoposting_enabled: bool = False
    instagram_comments_enabled: bool = True
    linkedin_connected: bool = False
    tiktok_connected: bool = False
    content_calendar_enabled: bool = False
    flower_price_adaptation_enabled: bool = False
    default_event_reminder_hours: int = Field(default=24, ge=1, le=2160)


class AutomationSettingsResponse(AutomationSettingsUpdate):
    tenant_id: str


class SocialPostingConnectionResponse(BaseModel):
    id: str
    company_id: str
    platform: Literal["instagram", "linkedin", "tiktok"]
    status: str
    external_account_id: str | None = None
    display_name: str | None = None
    connected_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    event_type: Literal["order", "campaign", "custom", "flower_supply"] = "order"
    event_at: datetime
    customer_id: str | None = Field(default=None, max_length=255)
    order_id: uuid.UUID | None = None
    flower_type: str | None = Field(default=None, max_length=255)
    base_price: str | None = Field(default=None, max_length=32)


class CalendarEventResponse(BaseModel):
    id: str
    company_id: str
    title: str
    description: str | None = None
    event_type: str
    event_at: datetime
    customer_id: str | None = None
    order_id: str | None = None
    flower_type: str | None = None
    base_price: str | None = None
    adjusted_price: str | None = None
    price_strategy: dict
    reminder_sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ContactResponse(BaseModel):
    id: str
    company_id: str
    channel: Literal["instagram", "whatsapp"]
    external_id: str
    display_name: str | None = None
    username: str | None = None
    phone: str | None = None
    segment: str = "lead"
    last_message_at: datetime | None = None
    last_user_message_at: datetime | None = None
    orders_count: int = 0
    total_revenue: str = "0.00"
    created_at: datetime | None = None


class LeadUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    email: str | None = Field(default=None, max_length=255)
    profile_link: str | None = Field(default=None, max_length=2000)
    interested_in: str | None = Field(default=None, max_length=2000)
    status: Literal["new", "interested", "contacted", "qualified", "enrolled", "not_interested", "lost", "archived"] | None = None
    lead_source: str | None = Field(default=None, max_length=64)
    ai_summary: str | None = Field(default=None, max_length=8000)
    tags: list[str] | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=8000)
    assigned_to: str | None = Field(default=None, max_length=255)
    next_follow_up_at: datetime | None = None


class LeadMessageResponse(BaseModel):
    id: str
    direction: Literal["inbound", "outbound"]
    text: str
    created_at: datetime


class LeadResponse(BaseModel):
    id: str
    company_id: str
    platform: Literal["instagram", "facebook", "tiktok", "whatsapp", "manual"]
    external_id: str
    conversation_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    phone: str | None = None
    email: str | None = None
    profile_link: str | None = None
    interested_in: str | None = None
    status: Literal["new", "interested", "contacted", "qualified", "enrolled", "not_interested", "lost", "archived"]
    lead_source: str
    first_interaction_at: datetime | None = None
    last_interaction_at: datetime | None = None
    ai_summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    assigned_to: str | None = None
    next_follow_up_at: datetime | None = None
    source_comment_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    manually_updated_at: datetime | None = None
    manually_updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class LeadProfileResponse(LeadResponse):
    conversation_history: list[LeadMessageResponse] = Field(default_factory=list)


class SocialPostDraftCreate(BaseModel):
    platform: Literal["instagram", "linkedin", "tiktok"] = "instagram"
    content_type: Literal["feed", "story", "reel", "photo", "video"] = "feed"
    title: str | None = Field(default=None, max_length=255)
    caption: str = Field(min_length=1, max_length=4000)
    media_urls: list[str] = Field(default_factory=list)
    scheduled_for: datetime | None = None
    metadata: dict = Field(default_factory=dict)


class SocialPostDraftResponse(BaseModel):
    id: str
    company_id: str
    platform: Literal["instagram", "linkedin", "tiktok"]
    content_type: Literal["feed", "story", "reel", "photo", "video"] = "feed"
    title: str | None = None
    caption: str
    media_urls: list[str]
    scheduled_for: datetime | None = None
    status: str
    zernio_post_id: str | None = None
    publish_result: dict
    published_at: datetime | None = None
    last_attempt_at: datetime | None = None
    error_message: str | None = None
    metadata: dict
    created_at: datetime
    updated_at: datetime


class SocialPostMediaUploadResponse(BaseModel):
    url: str
    content_type: str
    filename: str


class SocialPostScheduleRequest(BaseModel):
    scheduled_for: datetime


class TikTokIntegrationResponse(BaseModel):
    tenant_id: str
    connected: bool
    zernio_account_id: str | None = None
    tiktok_account_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    connected_at: datetime | None = None
    creator_info: dict | None = None


class LinkedInIntegrationResponse(BaseModel):
    tenant_id: str
    connected: bool
    zernio_account_id: str | None = None
    linkedin_account_id: str | None = None
    username: str | None = None
    display_name: str | None = None
    connected_at: datetime | None = None


class MessageResponse(BaseModel):
    id: str
    tenant_id: str
    channel: Literal["instagram", "whatsapp"] = "instagram"
    direction: Literal["inbound", "outbound"]
    sender_type: Literal["customer", "bot", "manager", "system"] | None = None
    manager_id: str | None = None
    text: str
    status: str
    external_message_id: str
    intent: str | None = None
    intent_confidence: float | None = None
    created_at: datetime | None = None


class ConversationResponse(BaseModel):
    id: str
    tenant_id: str
    channel: Literal["instagram", "whatsapp"] = "instagram"
    external_conversation_id: str
    customer_instagram_id: str | None = None
    customer_whatsapp_id: str | None = None
    customer_username: str | None = None
    customer_phone: str | None = None
    mode: Literal["bot", "human", "paused", "closed"] = "bot"
    assigned_manager_id: str | None = None
    bot_paused_at: datetime | None = None
    bot_paused_reason: str | None = None
    last_user_message_at: datetime | None = None
    messaging_window_expires_at: datetime | None = None
    last_manager_message_at: datetime | None = None
    last_bot_message_at: datetime | None = None
    status: str
    priority: str = "normal"
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    messages: list[MessageResponse]


class ConversationActionResponse(BaseModel):
    id: str
    tenant_id: str
    channel: Literal["instagram", "whatsapp"]
    mode: Literal["bot", "human", "paused", "closed"]
    assigned_manager_id: str | None = None
    bot_paused_at: datetime | None = None
    bot_paused_reason: str | None = None
    messaging_window_expires_at: datetime | None = None
    status: str
    priority: str


class ConversationSendMessageRequest(BaseModel):
    message_text: str = Field(min_length=1, max_length=4000)


class ConversationSendMessageResponse(BaseModel):
    message: MessageResponse
    conversation: ConversationActionResponse


class TelegramConnectResponse(BaseModel):
    connect_url: str


class TelegramStatusResponse(BaseModel):
    connected: bool
    username: str | None = None
    notifications_enabled: bool = False

class WhatsAppSessionResponse(BaseModel):
    company_id: str
    status: str
    has_qr: bool = False
    last_qr_at: str | None = None
    last_ready_at: str | None = None
    last_auth_failure: str | None = None
    last_disconnect_reason: str | None = None


class WhatsAppQrResponse(BaseModel):
    company_id: str
    status: str
    qr: str | None = None
    last_qr_at: str | None = None
    message: str | None = None

class ManagerCreate(BaseModel):
    channel: Literal["telegram"] = "telegram"
    recipient_id: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class ManagerUpdate(BaseModel):
    recipient_id: str = Field(default="telegram", min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class ManagerResponse(BaseModel):
    id: str
    company_id: str
    channel: Literal["telegram"]
    recipient_id: str
    display_name: str
    is_active: bool
    telegram_user_id: int | None = None
    telegram_chat_id: int | None = None
    telegram_username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language_code: str | None = None
    registered_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TelegramManagerConnectResponse(BaseModel):
    connect_url: str


class BroadcastCreate(BaseModel):
    target: Literal["instagram", "whatsapp", "both"]
    message_text: str = Field(min_length=1, max_length=4000)


class BroadcastCampaignResponse(BaseModel):
    id: str
    company_id: str
    target: Literal["instagram", "whatsapp", "both"]
    message_text: str
    status: str
    requested_count: int
    sent_count: int
    failed_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class OrderIntent(BaseModel):
    wants_order: bool = False
    course_guidance_requested: bool = False
    manager_handoff_requested: bool = False
    ready_to_submit: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    detected_language: str | None = None

    product_title: str | None = None
    product_price: str | None = None
    quantity: int | None = None

    customer_name: str | None = None
    customer_phone: str | None = None

    delivery_required: bool | None = None
    delivery_address: str | None = None
    delivery_time: str | None = None

    comment: str | None = None

    missing_fields: list[str] = Field(default_factory=list)
    next_question: str | None = None



class BusinessSettingsResponse(BaseModel):
    tenant_id: str
    business_type: BusinessType
    business_type_label: str
    supports_perishable_inventory: bool
    supports_custom_visual_requests: bool
    custom_item_label: str | None = None
    auto_discount_enabled: bool
    default_shelf_life_hours: int | None = None
    default_discount_after_hours: int | None = None
    default_discount_percent: str


class BusinessSettingsUpdate(BaseModel):
    business_type: BusinessType
    auto_discount_enabled: bool = False
    default_shelf_life_hours: int | None = Field(default=None, gt=0, le=24 * 365)
    default_discount_after_hours: int | None = Field(default=None, ge=0, le=24 * 365)
    default_discount_percent: str = Field(default="0", max_length=16)


class InventoryItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    quantity: int = Field(default=1, ge=0)
    unit_cost: str = Field(default="0")
    original_price: str = Field(default="0")
    shelf_life_hours: int | None = Field(default=None, gt=0)
    discount_after_hours: int | None = Field(default=None, ge=0)
    discount_percent: str | None = None


class InventoryItemResponse(BaseModel):
    id: str
    company_id: str
    title: str
    category: str | None = None
    quantity: int
    unit_cost: str
    original_price: str
    effective_price: str
    discount_percent: str
    shelf_life_hours: int | None = None
    discount_after_hours: int | None = None
    status: str
    received_at: datetime
    created_at: datetime
    updated_at: datetime


class CustomProductRequestCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=2000)
    budget: str | None = Field(default=None, max_length=255)
    customer_id: str | None = Field(default=None, max_length=255)
    channel: Literal["instagram", "whatsapp"] | None = None


class CustomProductRequestResponse(BaseModel):
    id: str
    company_id: str
    business_type: BusinessType
    title: str
    description: str
    budget: str | None = None
    generated_prompt: str
    generated_image_url: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


OrderStatus = Literal["new", "sent_to_manager", "accepted", "paid", "completed", "cancelled", "done"]


class CustomerOrderResponse(BaseModel):
    id: str
    company_id: str
    channel: str
    customer_id: str
    conversation_id: str | None = None
    source_message_id: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    product_title: str | None = None
    product_price: str | None = None
    quantity: int | None = None
    delivery_required: bool | None = None
    delivery_address: str | None = None
    delivery_time: str | None = None
    customer_comment: str | None = None
    raw_summary: str
    status: OrderStatus
    revenue_amount: str | None = None
    cost_amount: str | None = None
    gross_profit: str
    manager_notified_at: datetime | None = None
    paid_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CustomerOrderUpdate(BaseModel):
    status: OrderStatus | None = None
    revenue_amount: str | None = None
    cost_amount: str | None = None


class BusinessAnalyticsResponse(BaseModel):
    tenant_id: str
    business_type: BusinessType
    business_type_label: str
    total_orders: int
    completed_orders: int
    gross_revenue: str
    total_costs: str
    net_profit: str
    unique_customers: int
    repeat_customers: int
    inbound_messages: int
    outbound_messages: int
    inventory_value: str
    stale_inventory_items: int
    discounted_inventory_items: int
    custom_requests: int
    conversion_rate: float
    top_products: list[dict[str, str | int]] = Field(default_factory=list)
    top_customers: list[dict[str, str | int]] = Field(default_factory=list)


class MessageActivityDay(BaseModel):
    date: str
    inbound: int
    outbound: int
    active_customers: int


class MessageActivityChannel(BaseModel):
    channel: Literal["instagram", "whatsapp"]
    inbound: int
    outbound: int
    active_customers: int


class MessageActivityCustomer(BaseModel):
    customer_id: str
    customer_label: str
    channel: Literal["instagram", "whatsapp"]
    message_count: int
    today_message_count: int
    last_message_at: datetime | None = None


class MessageActivityResponse(BaseModel):
    tenant_id: str
    date_from: str
    date_to: str
    total_messages: int
    inbound_messages: int
    outbound_messages: int
    active_customers: int
    today_messages: int
    today_customers_count: int
    daily_activity: list[MessageActivityDay] = Field(default_factory=list)
    channel_activity: list[MessageActivityChannel] = Field(default_factory=list)
    top_customers: list[MessageActivityCustomer] = Field(default_factory=list)
    today_customers: list[MessageActivityCustomer] = Field(default_factory=list)


class InstagramCommentResponse(BaseModel):
    id: str
    company_id: str
    thread_id: str
    zernio_account_id: str
    platform_comment_id: str
    platform_post_id: str
    zernio_post_id: str | None = None
    parent_comment_id: str | None = None
    author_id: str
    author_username: str | None = None
    author_name: str | None = None
    author_picture: str | None = None
    text: str
    is_reply: bool
    is_ad_comment: bool
    ad_id: str | None = None
    ad_title: str | None = None
    status: Literal["new", "suggested", "replied", "ignored", "converted"]
    ai_suggested_reply: str | None = None
    ai_generated_at: datetime | None = None
    replied_at: datetime | None = None
    converted_at: datetime | None = None
    created_at: datetime
    inserted_at: datetime


class CommentThreadResponse(BaseModel):
    id: str
    company_id: str
    zernio_account_id: str
    platform_post_id: str
    zernio_post_id: str | None = None
    post_permalink: str | None = None
    post_caption: str | None = None
    comment_count: int
    inbound_comment_count: int
    replied_comment_count: int
    converted_comment_count: int
    conversion_rate: float
    last_comment_at: datetime | None = None
    updated_at: datetime
    comments: list[InstagramCommentResponse] = Field(default_factory=list)


class CommentAnalyticsResponse(BaseModel):
    tenant_id: str
    total_comments: int
    unique_commenters: int
    replied_comments: int
    converted_comments: int
    pending_comments: int
    conversion_rate: float
    top_commenters: list[dict[str, str | int]] = Field(default_factory=list)
    top_posts: list[dict[str, str | int | float | None]] = Field(default_factory=list)


class CommentStatusUpdate(BaseModel):
    status: Literal["new", "suggested", "replied", "ignored", "converted"]


class WhatsAppCloudIntegrationResponse(BaseModel):
    status: str
    tenant_id: str
    business_id: str | None = None
    waba_id: str
    phone_number_id: str
    display_phone_number: str | None = None
    verified_name: str | None = None
    quality_rating: str | None = None
    webhook_subscribed: bool = False
    connected: bool

    registered: bool = False
    pin_required: bool = False