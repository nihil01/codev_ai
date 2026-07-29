const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

export type BusinessType = 'confectionery' | 'flower_shop' | 'cafe_restaurant' | 'other';

export type Tenant = { id: string; name: string; slug: string; business_type: BusinessType; business_type_label: string; is_active: boolean; package_code: PackageCode; access_locked: boolean };
export type PackageCode = 'basic' | 'full';
export type CompanySubscription = {
  company_id: string;
  package_code: PackageCode;
  monthly_text_messages_limit?: number | null;
  monthly_voice_messages_limit?: number | null;
  autoposting_enabled: boolean;
  access_locked: boolean;
  locked_reason?: string | null;
  locked_at?: string | null;
  usage_period: string;
  text_messages_used: number;
  voice_messages_used: number;
  created_at?: string | null;
  updated_at?: string | null;
};
export type Channel = {
  id: string;
  tenant_id: string;
  platform: 'instagram' | 'whatsapp';
  external_account_id: string;
  display_name: string;
  is_enabled: boolean;
};
export type Message = {
  id: string;
  tenant_id: string;
  channel: 'instagram' | 'whatsapp';
  direction: 'inbound' | 'outbound';
  sender_type?: 'customer' | 'bot' | 'manager' | 'system' | null;
  manager_id?: string | null;
  text: string;
  status: string;
  external_message_id: string;
  intent?: string | null;
  intent_confidence?: number | null;
  created_at?: string;
};
export type Conversation = {
  id: string;
  tenant_id: string;
  channel: 'instagram' | 'whatsapp';
  external_conversation_id: string;
  customer_instagram_id?: string | null;
  customer_whatsapp_id?: string | null;
  customer_username?: string | null;
  customer_phone?: string | null;
  mode: 'bot' | 'human' | 'paused' | 'closed';
  assigned_manager_id?: string | null;
  bot_paused_at?: string | null;
  bot_paused_reason?: string | null;
  last_user_message_at?: string | null;
  messaging_window_expires_at?: string | null;
  last_manager_message_at?: string | null;
  last_bot_message_at?: string | null;
  status: string;
  priority: 'low' | 'normal' | 'high' | 'urgent' | string;
  last_message_at?: string | null;
  created_at?: string;
  messages: Message[];
};
export type BotSettings = {
  tenant_id: string;
  enabled?: boolean;
  system_prompt: string;
  handoff_keywords: string;
};

export type CommentPrompt = {
  tenant_id: string;
  title: string;
  system_prompt: string;
  version: number;
};

export type CommentStatus = 'new' | 'suggested' | 'replied' | 'ignored' | 'converted';

export type InstagramComment = {
  id: string;
  company_id: string;
  thread_id: string;
  zernio_account_id: string;
  platform_comment_id: string;
  platform_post_id: string;
  zernio_post_id?: string | null;
  parent_comment_id?: string | null;
  author_id: string;
  author_username?: string | null;
  author_name?: string | null;
  author_picture?: string | null;
  text: string;
  is_reply: boolean;
  is_ad_comment: boolean;
  ad_id?: string | null;
  ad_title?: string | null;
  status: CommentStatus;
  ai_suggested_reply?: string | null;
  ai_generated_at?: string | null;
  replied_at?: string | null;
  converted_at?: string | null;
  created_at: string;
  inserted_at: string;
};

export type CommentThread = {
  id: string;
  company_id: string;
  zernio_account_id: string;
  platform_post_id: string;
  zernio_post_id?: string | null;
  post_permalink?: string | null;
  post_caption?: string | null;
  comment_count: number;
  inbound_comment_count: number;
  replied_comment_count: number;
  converted_comment_count: number;
  conversion_rate: number;
  last_comment_at?: string | null;
  updated_at: string;
  comments: InstagramComment[];
};

export type CommentAnalytics = {
  tenant_id: string;
  total_comments: number;
  unique_commenters: number;
  replied_comments: number;
  converted_comments: number;
  pending_comments: number;
  conversion_rate: number;
  top_commenters: Array<{ author_id: string; label: string; comments_count: number; converted_count: number }>;
  top_posts: Array<{ platform_post_id: string; label: string; comments_count: number; converted_count: number }>;
};

export type AdminBotPrompt = {
  tenant_id: string;
  company_name: string;
  username?: string | null;
  title: string;
  system_prompt: string;
  version: number;
};

export type LoginResponse = {
  user_id: string;
  email: string;
  role: 'admin' | 'company_user' | string;
  company_id: string | null;
  token: string;
};

export type CurrentUser = {
  user_id: string;
  email: string;
  role: 'admin' | 'company_user' | string;
  company_id: string | null;

  ig_activated: boolean;
  wp_activated: boolean;

  ig_enabled: boolean;
  wp_enabled: boolean;
};

export type ChangePasswordPayload = {
  current_password: string;
  new_password: string;
};

export type ChangePasswordResponse = {
  ok: boolean;
};

export type CreateCompanyUserResponse = {
  user_id: string;
  email: string;
  company_id: string | null;
  company_name: string;
  business_type: BusinessType;
  business_type_label: string;
  temporary_password: string;
  package_code?: PackageCode;
};

export type BusinessSettings = {
  tenant_id: string;
  business_type: BusinessType;
  business_type_label: string;
  supports_perishable_inventory: boolean;
  supports_custom_visual_requests: boolean;
  custom_item_label?: string | null;
  auto_discount_enabled: boolean;
  default_shelf_life_hours?: number | null;
  default_discount_after_hours?: number | null;
  default_discount_percent: string;
};

export type BusinessSettingsUpdate = {
  business_type: BusinessType;
  auto_discount_enabled: boolean;
  default_shelf_life_hours?: number | null;
  default_discount_after_hours?: number | null;
  default_discount_percent: string;
};

export type AutomationSettings = {
  tenant_id: string;
  client_reminder_enabled: boolean;
  client_reminder_delay_minutes: number;
  client_reminder_message: string;
  autoposting_enabled: boolean;
  instagram_comments_enabled: boolean;
  linkedin_connected: boolean;
  tiktok_connected: boolean;
  content_calendar_enabled: boolean;
  flower_price_adaptation_enabled: boolean;
  default_event_reminder_hours: number;
};

export type SocialPostingConnection = {
  id: string;
  company_id: string;
  platform: 'instagram' | 'linkedin' | 'tiktok';
  status: string;
  external_account_id?: string | null;
  display_name?: string | null;
  connected_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type CalendarEventCreate = {
  title: string;
  description?: string | null;
  event_type: 'order' | 'campaign' | 'custom' | 'flower_supply';
  event_at: string;
  customer_id?: string | null;
  order_id?: string | null;
  flower_type?: string | null;
  base_price?: string | null;
};

export type CalendarEvent = CalendarEventCreate & {
  id: string;
  company_id: string;
  adjusted_price?: string | null;
  price_strategy: Record<string, unknown>;
  reminder_sent_at?: string | null;
  created_at: string;
  updated_at: string;
};


export type Contact = {
  id: string;
  company_id: string;
  channel: 'instagram' | 'whatsapp';
  external_id: string;
  display_name?: string | null;
  username?: string | null;
  phone?: string | null;
  segment: 'lead' | 'customer' | 'hot' | string;
  last_message_at?: string | null;
  last_user_message_at?: string | null;
  orders_count: number;
  total_revenue: string;
  created_at?: string | null;
};

export type SocialPostDraftCreate = {
  platform: 'instagram' | 'linkedin' | 'tiktok';
  title?: string | null;
  caption: string;
  media_urls: string[];
  scheduled_for?: string | null;
  metadata?: Record<string, unknown>;
};

export type SocialPostMediaUploadResponse = {
  url: string;
  content_type: string;
  filename: string;
};

export type SocialPostDraft = SocialPostDraftCreate & {
  id: string;
  company_id: string;
  status: string;
  zernio_post_id?: string | null;
  publish_result: Record<string, unknown>;
  published_at?: string | null;
  last_attempt_at?: string | null;
  error_message?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type LinkedInIntegration = {
  tenant_id: string;
  connected: boolean;
  zernio_account_id?: string | null;
  linkedin_account_id?: string | null;
  username?: string | null;
  display_name?: string | null;
  connected_at?: string | null;
};

export type TikTokIntegration = {
  tenant_id: string;
  connected: boolean;
  zernio_account_id?: string | null;
  tiktok_account_id?: string | null;
  username?: string | null;
  display_name?: string | null;
  connected_at?: string | null;
  creator_info?: Record<string, unknown> | null;
};

export type BusinessAnalytics = {
  tenant_id: string;
  business_type: BusinessType;
  business_type_label: string;
  total_orders: number;
  completed_orders: number;
  gross_revenue: string;
  total_costs: string;
  net_profit: string;
  unique_customers: number;
  repeat_customers: number;
  inbound_messages: number;
  outbound_messages: number;
  inventory_value: string;
  stale_inventory_items: number;
  discounted_inventory_items: number;
  custom_requests: number;
  conversion_rate: number;
  top_products?: Array<{ product_title: string; quantity_sold: number; orders_count: number; revenue: string }>;
  top_customers?: Array<{ customer_id: string; customer_label: string; orders_count: number; items_count: number; message_count?: number; revenue: string }>;
};

export type OrderStatus = 'new' | 'sent_to_manager' | 'accepted' | 'paid' | 'completed' | 'cancelled' | 'done';
export type VisibleOrderStatus = 'paid' | 'cancelled';

export type CustomerOrder = {
  id: string;
  company_id: string;
  channel: string;
  customer_id: string;
  conversation_id?: string | null;
  source_message_id?: string | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  product_title?: string | null;
  product_price?: string | null;
  quantity?: number | null;
  delivery_required?: boolean | null;
  delivery_address?: string | null;
  delivery_time?: string | null;
  customer_comment?: string | null;
  raw_summary: string;
  status: OrderStatus;
  revenue_amount?: string | null;
  cost_amount?: string | null;
  gross_profit: string;
  manager_notified_at?: string | null;
  paid_at?: string | null;
  completed_at?: string | null;
  cancelled_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type CustomerOrderUpdate = {
  status?: OrderStatus | null;
  revenue_amount?: string | null;
  cost_amount?: string | null;
};

export type InstagramIntegration = {
  tenant_id: string;
  company_id?: string;

  ig_activated: boolean;
  ig_enabled: boolean;

  wp_activated: boolean;
  wp_enabled: boolean;

  user_id?: string | null;
  username?: string | null;
  display_name?: string | null;
  account_type?: string | null;
  profile_picture_url?: string | null;
};

export type InstagramConnectUrlResponse = {
  auth_url: string;
};

export type TelegramStatus = {
  connected: boolean;
  username?: string | null;
  notifications_enabled: boolean;
};

export type TelegramConnectResponse = {
  connect_url: string;
};

export type ConversationActionResponse = {
  id: string;
  tenant_id: string;
  channel: 'instagram' | 'whatsapp';
  mode: 'bot' | 'human' | 'paused' | 'closed';
  assigned_manager_id?: string | null;
  bot_paused_at?: string | null;
  bot_paused_reason?: string | null;
  messaging_window_expires_at?: string | null;
  status: string;
  priority: string;
};

export type ConversationSendMessageResponse = {
  message: Message;
  conversation: ConversationActionResponse;
};

export type KnowledgeEntry = {
  id: string;
  company_id: string;
  entry_type: 'text' | 'product_photo';
  title: string;
  content: string;
  source_url?: string | null;
  image_url?: string | null;
  image_mime_type?: string | null;
  quantity_available?: number | null;
  ai_generated_description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type WhatsAppCloudIntegration = {
  status: string;
  tenant_id: string;
  business_id?: string | null;
  waba_id: string;
  phone_number_id: string;
  display_phone_number?: string | null;
  verified_name?: string | null;
  quality_rating?: string | null;
  webhook_subscribed: boolean;
  connected: boolean;
  registered?: boolean;
  pin_required?: boolean;
};

export type Manager = {
  id: string;
  company_id: string;
  channel: 'telegram';
  recipient_id: string;
  display_name: string;
  is_active: boolean;
  telegram_user_id?: number | null;
  telegram_chat_id?: number | null;
  telegram_username?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  language_code?: string | null;
  registered_at?: string | null;
  last_seen_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type TelegramManagerConnectResponse = {
  connect_url: string;
};

export type BroadcastCampaign = {
  id: string;
  company_id: string;
  target: 'instagram' | 'whatsapp' | 'both';
  message_text: string;
  status: string;
  requested_count: number;
  sent_count: number;
  failed_count: number;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};


function authToken(): string | null {
  return sessionStorage.getItem('token') ?? localStorage.getItem('token');
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData;

  const headers = new Headers(init.headers);

  if (!isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const token = authToken();

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;

    try {
      const data = await response.json();
      message = data.detail
        ? `${response.status} ${typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)}`
        : JSON.stringify(data);
    } catch {
      const text = await response.text();
      if (text) {
        message = `${response.status} ${text}`;
      }
    }

    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function requestForm<T>(path: string, formData: FormData, init?: RequestInit): Promise<T> {
  const token = authToken();
  const headers: Record<string, string> = {};

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    method: init?.method ?? 'POST',
    body: formData,
    headers: {
      ...headers,
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      message = data.detail ? `${response.status} ${data.detail}` : JSON.stringify(data);
    } catch {
      const text = await response.text();
      if (text) message = `${response.status} ${text}`;
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    }),

  getCurrentUser: () => request<CurrentUser>('/api/auth/me'),
  changePassword: (payload: ChangePasswordPayload) =>
    request<ChangePasswordResponse>('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  createCompanyUser: (email: string, instagram_account_name: string, temporary_password: string, business_type: BusinessType = 'other', package_code: PackageCode = 'basic') =>
    request<CreateCompanyUserResponse>('/api/auth/users', {
      method: 'POST',
      body: JSON.stringify({ email, instagram_account_name, temporary_password, business_type, package_code })
    }),

  tenants: () => request<Tenant[]>('/api/tenants'),
  companySubscription: (tenantId: string) => request<CompanySubscription>(`/api/admin/tenants/${tenantId}/subscription`),
  updateCompanySubscription: (tenantId: string, payload: { package_code: PackageCode; access_locked: boolean; locked_reason?: string | null }) =>
    request<CompanySubscription>(`/api/admin/tenants/${tenantId}/subscription`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  createTenant: (payload: { name: string; slug: string; business_type?: BusinessType }) =>
    request<Tenant>('/api/tenants', { method: 'POST', body: JSON.stringify(payload) }),
  businessSettings: (tenantId: string) => request<BusinessSettings>(`/api/tenants/${tenantId}/business-settings`),
  updateBusinessSettings: (tenantId: string, payload: BusinessSettingsUpdate) =>
    request<BusinessSettings>(`/api/tenants/${tenantId}/business-settings`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  businessAnalytics: (tenantId: string) => request<BusinessAnalytics>(`/api/tenants/${tenantId}/analytics`),
  automationSettings: (tenantId: string) => request<AutomationSettings>(`/api/tenants/${tenantId}/automation-settings`),
  updateAutomationSettings: (tenantId: string, payload: AutomationSettings) =>
    request<AutomationSettings>(`/api/tenants/${tenantId}/automation-settings`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  socialConnections: (tenantId: string) => request<SocialPostingConnection[]>(`/api/tenants/${tenantId}/social-connections`),
  contacts: (tenantId: string, filters?: { q?: string; segment?: 'all' | 'lead' | 'customer' | 'hot' }) => {
    const params = new URLSearchParams();
    if (filters?.q) params.set('q', filters.q);
    if (filters?.segment && filters.segment !== 'all') params.set('segment', filters.segment);
    const query = params.toString();
    return request<Contact[]>(`/api/tenants/${tenantId}/contacts${query ? `?${query}` : ''}`);
  },
  socialPostDrafts: (tenantId: string) => request<SocialPostDraft[]>(`/api/tenants/${tenantId}/social-posts`),
  uploadSocialPostMedia: (tenantId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<SocialPostMediaUploadResponse>(`/api/tenants/${tenantId}/social-posts/media`, {
      method: 'POST',
      body: formData,
    });
  },
  createSocialPostDraft: (tenantId: string, payload: SocialPostDraftCreate) =>
    request<SocialPostDraft>(`/api/tenants/${tenantId}/social-posts`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  publishSocialPost: (tenantId: string, postId: string) =>
    request<SocialPostDraft>(`/api/tenants/${tenantId}/social-posts/${postId}/publish`, { method: 'POST' }),
  scheduleSocialPost: (tenantId: string, postId: string, scheduledFor: string) =>
    request<SocialPostDraft>(`/api/tenants/${tenantId}/social-posts/${postId}/schedule`, {
      method: 'POST',
      body: JSON.stringify({ scheduled_for: scheduledFor }),
    }),
  rejectSocialPost: (tenantId: string, postId: string) =>
    request<SocialPostDraft>(`/api/tenants/${tenantId}/social-posts/${postId}/reject`, { method: 'POST' }),
  deleteSocialPost: (tenantId: string, postId: string) =>
    request<void>(`/api/tenants/${tenantId}/social-posts/${postId}`, { method: 'DELETE' }),
  linkedinIntegration: (tenantId: string) => request<LinkedInIntegration>(`/api/tenants/${tenantId}/linkedin`),
  connectLinkedIn: (tenantId: string) => request<InstagramConnectUrlResponse>(`/api/tenants/${tenantId}/linkedin/connect`, { method: 'POST', body: JSON.stringify({}) }),
  disconnectLinkedIn: (tenantId: string) => request<LinkedInIntegration>(`/api/tenants/${tenantId}/linkedin`, { method: 'DELETE' }),
  tiktokIntegration: (tenantId: string) => request<TikTokIntegration>(`/api/tenants/${tenantId}/tiktok`),
  connectTikTok: (tenantId: string) => request<InstagramConnectUrlResponse>(`/api/tenants/${tenantId}/tiktok/connect`, { method: 'POST', body: JSON.stringify({}) }),
  disconnectTikTok: (tenantId: string) => request<TikTokIntegration>(`/api/tenants/${tenantId}/tiktok`, { method: 'DELETE' }),
  calendarEvents: (tenantId: string) => request<CalendarEvent[]>(`/api/tenants/${tenantId}/calendar-events`),
  createCalendarEvent: (tenantId: string, payload: CalendarEventCreate) =>
    request<CalendarEvent>(`/api/tenants/${tenantId}/calendar-events`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  commentPrompt: (tenantId: string) => request<CommentPrompt>(`/api/admin/tenants/${tenantId}/comment-prompt`),
  updateCommentPrompt: (tenantId: string, payload: { system_prompt: string; title?: string }) =>
    request<CommentPrompt>(`/api/admin/tenants/${tenantId}/comment-prompt`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  commentThreads: (tenantId: string, status?: CommentStatus | 'all') => {
    const params = new URLSearchParams();
    if (status && status !== 'all') params.set('status', status);
    const query = params.toString();
    return request<CommentThread[]>(`/api/tenants/${tenantId}/comments${query ? `?${query}` : ''}`);
  },
  commentAnalytics: (tenantId: string) => request<CommentAnalytics>(`/api/tenants/${tenantId}/comments/analytics`),
  updateCommentStatus: (tenantId: string, commentId: string, status: CommentStatus) =>
    request<InstagramComment>(`/api/tenants/${tenantId}/comments/${commentId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  sendCommentPrivateReply: (tenantId: string, commentId: string, message: string) =>
    request<{ status: string; reply: unknown }>(`/api/tenants/${tenantId}/comments/${commentId}/private-reply`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  getAutoReplySettings: (tenantId: string) =>
    request<{ enabled: boolean }>(`/api/tenants/${tenantId}/automation-settings/auto-reply`),
  updateAutoReplySettings: (tenantId: string, enabled: boolean) =>
    request<{ enabled: boolean }>(`/api/tenants/${tenantId}/automation-settings/auto-reply`, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),
  customerOrders: (tenantId: string, filters?: { status?: OrderStatus | 'all'; from?: string; to?: string; limit?: number; offset?: number }) => {
    const params = new URLSearchParams();
    if (filters?.status && filters.status !== 'all') params.set('status', filters.status);
    if (filters?.from) params.set('from_date', filters.from);
    if (filters?.to) params.set('to_date', filters.to);
    if (filters?.limit) params.set('limit', String(filters.limit));
    if (filters?.offset) params.set('offset', String(filters.offset));
    const query = params.toString();
    return request<CustomerOrder[]>(`/api/tenants/${tenantId}/orders${query ? `?${query}` : ''}`);
  },
  updateCustomerOrder: (tenantId: string, orderId: string, payload: CustomerOrderUpdate) =>
    request<CustomerOrder>(`/api/tenants/${tenantId}/orders/${orderId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    }),
  channels: (tenantId?: string) =>
    request<Channel[]>(`/api/channels${tenantId ? `?tenant_id=${tenantId}` : ''}`),
  createChannel: (payload: {
    tenant_id: string;
    platform: 'instagram' | 'whatsapp';
    external_account_id: string;
    display_name: string;
  }) => request<Channel>('/api/channels', { method: 'POST', body: JSON.stringify(payload) }),
  conversations: (tenantId: string, filters?: { from?: string; to?: string; customer?: string; channel?: 'all' | 'instagram' | 'whatsapp' }) => {
    const params = new URLSearchParams({ tenant_id: tenantId });
    if (filters?.from) params.set('from_date', filters.from);
    if (filters?.to) params.set('to_date', filters.to);
    if (filters?.customer) params.set('customer', filters.customer);
    if (filters?.channel && filters.channel !== 'all') params.set('channel', filters.channel);
    return request<Conversation[]>(`/api/conversations?${params.toString()}`);
  },
  takeConversation: (tenantId: string, channel: 'instagram' | 'whatsapp', conversationId: string) =>
    request<ConversationActionResponse>(`/api/tenants/${tenantId}/conversations/${channel}/${conversationId}/take`, { method: 'POST' }),
  returnConversationToBot: (tenantId: string, channel: 'instagram' | 'whatsapp', conversationId: string) =>
    request<ConversationActionResponse>(`/api/tenants/${tenantId}/conversations/${channel}/${conversationId}/return-bot`, { method: 'POST' }),
  pauseConversation: (tenantId: string, channel: 'instagram' | 'whatsapp', conversationId: string) =>
    request<ConversationActionResponse>(`/api/tenants/${tenantId}/conversations/${channel}/${conversationId}/pause`, { method: 'POST' }),
  sendConversationMessage: (tenantId: string, channel: 'instagram' | 'whatsapp', conversationId: string, messageText: string) =>
    request<ConversationSendMessageResponse>(`/api/tenants/${tenantId}/conversations/${channel}/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ message_text: messageText })
    }),
  closeConversation: (tenantId: string, channel: 'instagram' | 'whatsapp', conversationId: string) =>
    request<ConversationActionResponse>(`/api/tenants/${tenantId}/conversations/${channel}/${conversationId}/close`, { method: 'POST' }),
  telegramStatus: () => request<TelegramStatus>('/api/me/telegram'),
  createTelegramConnectLink: () => request<TelegramConnectResponse>('/api/me/telegram/connect-link', { method: 'POST' }),
  disconnectTelegram: () => request<TelegramStatus>('/api/me/telegram', { method: 'DELETE' }),
  botSettings: (tenantId: string) => request<BotSettings>(`/api/tenants/${tenantId}/bot-settings`),
  updateBotSettings: (tenantId: string, payload: { enabled?: boolean; handoff_keywords?: string }) =>
    request<BotSettings>(`/api/tenants/${tenantId}/bot-settings`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    }),
  botPrompt: (tenantId: string) =>
    request<AdminBotPrompt>(`/api/tenants/${tenantId}/bot-prompt`),
  updateBotPrompt: (tenantId: string, payload: { system_prompt: string; title?: string }) =>
    request<AdminBotPrompt>(`/api/tenants/${tenantId}/bot-prompt`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  adminBotPrompt: (tenantId: string) =>
    request<AdminBotPrompt>(`/api/admin/tenants/${tenantId}/bot-prompt`),
  updateAdminBotPrompt: (tenantId: string, payload: { system_prompt: string; title?: string }) =>
    request<AdminBotPrompt>(`/api/admin/tenants/${tenantId}/bot-prompt`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  instagramIntegration: (tenantId: string) =>
    request<InstagramIntegration>(`/api/tenants/${tenantId}/instagram`),
  connectInstagram: (tenantId: string) =>
    request<InstagramConnectUrlResponse>(`/api/tenants/${tenantId}/instagram/connect`, {
      method: 'POST',
      body: JSON.stringify({})
    }),
  connectWhatsAppCloud: (tenantId: string) =>
    request<InstagramConnectUrlResponse>(`/api/tenants/${tenantId}/whatsapp-cloud/connect`, {
      method: 'POST',
      body: JSON.stringify({})
    }),
  updateInstagramBotStatus: (tenantId: string, enabled: boolean) =>
    request<InstagramIntegration>(`/api/tenants/${tenantId}/instagram/bot-status`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled })
    }),
  deauthorizeInstagram: (tenantId: string) =>
    request<InstagramIntegration>(`/api/tenants/${tenantId}/instagram`, {
      method: 'DELETE'
    }),
  knowledgeEntries: (tenantId: string) =>
    request<KnowledgeEntry[]>(`/api/tenants/${tenantId}/knowledge-base`),
  createKnowledgeEntry: (
  tenantId: string,
  payload: {
    title: string;
    content: string;
    source_url?: string;
    quantity_available?: number | null;
  },
) => {
  return request<KnowledgeEntry>(`/api/tenants/${tenantId}/knowledge-base`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
},
  uploadKnowledgePhoto: (
  tenantId: string,
  title: string,
  file: File,
  price?: string,
  quantityAvailable?: string,
  deliveryAvailable?: boolean,
  descriptionLanguage: 'az' | 'en' | 'ru' = 'az',
) => {
  const formData = new FormData();

  formData.append('title', title);
  formData.append('file', file);

  if (price) {
    formData.append('price', price);
  }

  if (quantityAvailable) {
    formData.append('quantity_available', quantityAvailable);
  }

  formData.append('delivery_available', deliveryAvailable ? '1' : '0');
  formData.append('description_language', descriptionLanguage);

  return request<KnowledgeEntry>(`/api/tenants/${tenantId}/knowledge-base/photos`, {
    method: 'POST',
    body: formData,
  });
},
  deleteKnowledgeEntry: (tenantId: string, entryId: string) =>
    request<void>(`/api/tenants/${tenantId}/knowledge-base/${entryId}`, {
      method: 'DELETE'
    }),

  managers: (tenantId: string) =>
    request<Manager[]>(`/api/tenants/${tenantId}/managers`),

  createTelegramManagerConnectLink: (tenantId: string) =>
    request<TelegramManagerConnectResponse>(`/api/tenants/${tenantId}/managers/telegram/connect-link`, {
      method: 'POST',
    }),

  createManager: (tenantId: string, payload: {
    channel: 'telegram';
    recipient_id: string;
    display_name: string;
    is_active: boolean;
  }) => request<Manager>(`/api/tenants/${tenantId}/managers`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }),

  updateManager: (tenantId: string, managerId: string, payload: {
    recipient_id: string;
    display_name: string;
    is_active: boolean;
  }) => request<Manager>(`/api/tenants/${tenantId}/managers/${managerId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  }),

  deleteManager: (tenantId: string, managerId: string) =>
    request<void>(`/api/tenants/${tenantId}/managers/${managerId}`, {
      method: 'DELETE',
    }),

  // broadcasts: (tenantId: string) =>
  //   request<BroadcastCampaign[]>(`/api/tenants/${tenantId}/broadcasts`),
  //
  // sendBroadcast: (tenantId: string, payload: {
  //   target: 'instagram' | 'whatsapp' | 'both';
  //   message_text: string;
  // }) => request<BroadcastCampaign>(`/api/tenants/${tenantId}/broadcasts`, {
  //   method: 'POST',
  //   body: JSON.stringify(payload),
  // }),

getWhatsAppCloudStatus: (tenantId: string) =>
  request<WhatsAppCloudIntegration>(
    `/api/tenants/${tenantId}/whatsapp-cloud/status`,
  ),

disconnectWhatsAppCloud: (tenantId: string) =>
  request<WhatsAppCloudIntegration>(
    `/api/tenants/${tenantId}/whatsapp-cloud`,
    {
      method: 'DELETE',
    },
  ),

};
