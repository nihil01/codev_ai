import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { CalendarDays, CheckCircle2, Clock, History, ImageUp, Play, Send, Sparkles, Trash2, XCircle } from 'lucide-react';
import { api } from '../../api';
import type { KnowledgeEntry, SocialPostDraft, SocialPostDraftCreate } from '../../api';
import { cardClass, inputClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { Field } from '../../components/ui/Field';
import { Spinner } from '../../components/ui/Spinner';
import { useI18n } from '../../i18n';

type Platform = 'instagram' | 'tiktok';
type PostsTab = 'active' | 'history';

type PostsSchedulerPanelProps = {
  companyId?: string | null;
  products: KnowledgeEntry[];
  onError?: (message: string) => void;
  onNotice?: (message: string) => void;
};

const platformOptions: Array<{ value: Platform; label: string }> = [
  { value: 'instagram', label: 'Instagram' },
  { value: 'tiktok', label: 'TikTok' },
];

const BAKU_TIMEZONE = 'Asia/Baku';
const BAKU_GMT_LABEL = 'GMT+4';
const hours24 = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, '0'));
const minuteOptions = Array.from({ length: 12 }, (_, index) => String(index * 5).padStart(2, '0'));

function formatDate(value?: string | null) {
  if (!value) return '—';
  return `${new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short', hourCycle: 'h23', timeZone: BAKU_TIMEZONE }).format(new Date(value))} (${BAKU_GMT_LABEL})`;
}

function bakuParts(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: BAKU_TIMEZONE,
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(date);
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? '00';
  return { year: value('year'), month: value('month'), day: value('day'), hour: value('hour'), minute: value('minute') };
}

function todayBakuKey() {
  const parts = bakuParts();
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function defaultBakuSchedule() {
  const parts = bakuParts();
  let hour = Number(parts.hour);
  let minute = Math.ceil((Number(parts.minute) + 1) / 5) * 5;
  let day = `${parts.year}-${parts.month}-${parts.day}`;
  if (minute >= 60) {
    minute = 0;
    hour += 1;
  }
  if (hour >= 24) {
    const next = dateFromKey(day);
    next.setDate(next.getDate() + 1);
    day = dateKey(next);
    hour = 0;
  }
  return { day, time: `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}` };
}

function currentBakuMinuteOfDay() {
  const parts = bakuParts();
  return Number(parts.hour) * 60 + Number(parts.minute);
}

function dateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function dateFromKey(key: string) {
  const [year, month, day] = key.split('-').map(Number);
  return new Date(year, month - 1, day);
}

function selectedMinuteOfDay(time: string) {
  const [hour = '0', minute = '0'] = time.split(':');
  return Number(hour) * 60 + Number(minute);
}

function isScheduleInPast(day: string, time: string) {
  const today = todayBakuKey();
  if (day < today) return true;
  if (day > today) return false;
  return selectedMinuteOfDay(time) <= currentBakuMinuteOfDay();
}

function toBakuIsoDatetime(day: string, time: string) {
  if (!day || !time) return '';
  return `${day}T${time}:00+04:00`;
}

function monthMatrix(anchor: Date) {
  const year = anchor.getFullYear();
  const month = anchor.getMonth();
  const first = new Date(year, month, 1);
  const start = new Date(first);
  const mondayOffset = (first.getDay() + 6) % 7;
  start.setDate(first.getDate() - mondayOffset);
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

function isVideoUrl(url: string) {
  return /\.(mp4|mov|webm|m4v)(\?|$)/i.test(url);
}

function isHistoryPost(post: SocialPostDraft) {
  if (post.status === 'published' || post.status === 'rejected' || post.published_at) return true;
  if (post.status === 'scheduled' && post.zernio_post_id && post.scheduled_for) {
    return new Date(post.scheduled_for).getTime() <= Date.now();
  }
  return false;
}

export function PostsSchedulerPanel({ companyId, products, onError, onNotice }: PostsSchedulerPanelProps) {
  const { t } = useI18n();
  const initialSchedule = useMemo(() => defaultBakuSchedule(), []);
  const [posts, setPosts] = useState<SocialPostDraft[]>([]);
  const [activeTab, setActiveTab] = useState<PostsTab>('active');
  const [loading, setLoading] = useState(false);
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [manualTitle, setManualTitle] = useState('');
  const [manualCaption, setManualCaption] = useState('');
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>(['instagram']);
  const [selectedDay, setSelectedDay] = useState(initialSchedule.day);
  const [selectedTime, setSelectedTime] = useState(initialSchedule.time);
  const [visibleMonth, setVisibleMonth] = useState(() => dateFromKey(initialSchedule.day));
  const [savingManual, setSavingManual] = useState(false);
  const [publishingPostId, setPublishingPostId] = useState<string | null>(null);
  const [deletingPostId, setDeletingPostId] = useState<string | null>(null);
  const [reviewingPostId, setReviewingPostId] = useState<string | null>(null);

  const productOptions = useMemo(() => products.filter((entry) => entry.image_url), [products]);
  const [productId, setProductId] = useState('');
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiCaption, setAiCaption] = useState('');
  const [generatingVideo, setGeneratingVideo] = useState(false);

  const selectedProduct = productOptions.find((product) => product.id === productId);
  const scheduleIsPast = isScheduleInPast(selectedDay, selectedTime);
  const selectedSchedule = toBakuIsoDatetime(selectedDay, selectedTime);
  const days = useMemo(() => monthMatrix(visibleMonth), [visibleMonth]);
  const [selectedHour = '00', selectedMinute = '00'] = selectedTime.split(':');
  const activePosts = useMemo(() => posts.filter((post) => !isHistoryPost(post)).slice(0, 20), [posts]);
  const historyPosts = useMemo(() => posts.filter(isHistoryPost).slice(0, 30), [posts]);
  const visiblePosts = activeTab === 'active' ? activePosts : historyPosts;

  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;
    setLoading(true);
    api.socialPostDrafts(companyId)
      .then((rows) => { if (!cancelled) setPosts(rows); })
      .catch((err) => { if (!cancelled) onError?.(err instanceof Error ? err.message : String(err)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [companyId]);

  useEffect(() => {
    if (!productId && productOptions[0]) setProductId(productOptions[0].id);
  }, [productId, productOptions]);

  function togglePlatform(platform: Platform) {
    setSelectedPlatforms((current) => current.includes(platform) ? (current.length > 1 ? current.filter((item) => item !== platform) : current) : [...current, platform]);
  }

  async function createDraftsForPlatforms(base: Omit<SocialPostDraftCreate, 'platform'>) {
    if (!companyId) return [];
    const created: SocialPostDraft[] = [];
    for (const platform of selectedPlatforms) created.push(await api.createSocialPostDraft(companyId, { ...base, platform }));
    setPosts((current) => [...created, ...current]);
    return created;
  }

  async function saveUploadedPost() {
    if (!companyId || !mediaFile || !manualCaption.trim() || selectedPlatforms.length === 0) return;
    if (scheduleIsPast) return onError?.(t('posts.pastWarning'));
    setSavingManual(true); onError?.(''); onNotice?.('');
    try {
      const uploaded = await api.uploadSocialPostMedia(companyId, mediaFile);
      await createDraftsForPlatforms({
        title: manualTitle.trim() || mediaFile.name,
        caption: manualCaption.trim(),
        media_urls: [uploaded.url],
        scheduled_for: selectedSchedule,
        metadata: { source: 'manual_upload', filename: uploaded.filename, content_type: uploaded.content_type },
      });
      setMediaFile(null); setManualTitle(''); setManualCaption('');
      onNotice?.(t('posts.uploaded'));
    } catch (err) { onError?.(err instanceof Error ? err.message : String(err)); }
    finally { setSavingManual(false); }
  }

  async function generateReplicateVideo() {
    if (!companyId || !selectedProduct || !aiPrompt.trim() || !aiCaption.trim() || selectedPlatforms.length === 0) return;
    setGeneratingVideo(true); onError?.(''); onNotice?.('');
    try {
      const result = await api.createReplicateProductVideo(companyId, {
        product_id: selectedProduct.id,
        platforms: selectedPlatforms,
        prompt: aiPrompt.trim(),
        caption: aiCaption.trim(),
        title: `AI video: ${selectedProduct.title}`,
        scheduled_for: null,
        duration: 5,
        aspect_ratio: '9:16',
      });
      setPosts((current) => [...result.drafts, ...current]);
      setAiPrompt(''); setAiCaption(''); setActiveTab('active');
      onNotice?.(t('posts.videoReady'));
    } catch (err) { onError?.(err instanceof Error ? err.message : String(err)); }
    finally { setGeneratingVideo(false); }
  }

  async function publishPost(postId: string) {
    if (!companyId) return;
    setPublishingPostId(postId); onError?.(''); onNotice?.('');
    try {
      const updated = await api.publishSocialPost(companyId, postId);
      setPosts((current) => current.map((item) => item.id === postId ? updated : item));
      onNotice?.(t('posts.scheduled'));
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
      api.socialPostDrafts(companyId).then(setPosts).catch(() => undefined);
    } finally { setPublishingPostId(null); }
  }

  async function approveAndSchedule(postId: string) {
    if (!companyId) return;
    if (scheduleIsPast) return onError?.(t('posts.pastWarning'));
    setReviewingPostId(postId); onError?.(''); onNotice?.('');
    try {
      const updated = await api.scheduleSocialPost(companyId, postId, selectedSchedule);
      setPosts((current) => current.map((item) => item.id === postId ? updated : item));
      onNotice?.(t('posts.scheduled'));
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
      api.socialPostDrafts(companyId).then(setPosts).catch(() => undefined);
    } finally { setReviewingPostId(null); }
  }

  async function rejectPost(postId: string) {
    if (!companyId) return;
    setReviewingPostId(postId); onError?.(''); onNotice?.('');
    try {
      const updated = await api.rejectSocialPost(companyId, postId);
      setPosts((current) => current.map((item) => item.id === postId ? updated : item));
      onNotice?.(t('posts.rejected'));
    } catch (err) { onError?.(err instanceof Error ? err.message : String(err)); }
    finally { setReviewingPostId(null); }
  }

  async function deletePost(post: SocialPostDraft) {
    if (!companyId || post.status === 'published' || post.published_at || isHistoryPost(post)) return;
    if (!window.confirm(t('posts.deleteConfirm'))) return;
    setDeletingPostId(post.id); onError?.(''); onNotice?.('');
    try {
      await api.deleteSocialPost(companyId, post.id);
      setPosts((current) => current.filter((item) => item.id !== post.id));
      onNotice?.(t('posts.deleted'));
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
      api.socialPostDrafts(companyId).then(setPosts).catch(() => undefined);
    } finally { setDeletingPostId(null); }
  }

  if (loading) return <div className={cardClass}><Spinner label="Загружаю посты..." /></div>;

  return (
    <section className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={cardClass}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <span className="rounded-2xl bg-[#f0f4fe] p-3 text-[#145aff]"><Send size={22} /></span>
            <div>
              <h2 className="text-xl font-semibold text-[#020520]">{t('posts.title')}</h2>
              <p className="mt-1 text-sm text-[#696a72]">{t('posts.subtitle')}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {platformOptions.map((platform) => (
              <button key={platform.value} type="button" onClick={() => togglePlatform(platform.value)} className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${selectedPlatforms.includes(platform.value) ? 'border-[#145aff] bg-[#145aff] text-white' : 'border-[#e2e4e9] bg-white text-[#020520]'}`}>{platform.label}</button>
            ))}
          </div>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-[#e2e4e9] p-4">
            <div className="flex items-center justify-between">
              <button type="button" className={secondaryButtonClass} onClick={() => setVisibleMonth(new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1))}>←</button>
              <div className="text-center">
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-[#145aff]">{t('posts.scheduleEyebrow')}</p>
                <h3 className="text-lg font-semibold text-[#020520]">{new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric', timeZone: BAKU_TIMEZONE }).format(visibleMonth)}</h3>
                <p className="mt-1 text-xs text-[#696a72]">{t('posts.scheduleHint')}</p>
              </div>
              <button type="button" className={secondaryButtonClass} onClick={() => setVisibleMonth(new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1))}>→</button>
            </div>
            <div className="mt-4 grid grid-cols-7 gap-2 text-center text-xs font-semibold uppercase text-[#696a72]">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => <span key={day}>{day}</span>)}</div>
            <div className="mt-2 grid grid-cols-7 gap-2">
              {days.map((day) => {
                const key = dateKey(day); const active = key === selectedDay; const muted = day.getMonth() !== visibleMonth.getMonth(); const past = key < todayBakuKey();
                return <button key={key} type="button" disabled={past} onClick={() => setSelectedDay(key)} className={`aspect-square rounded-2xl border text-sm font-semibold transition ${active ? 'border-[#145aff] bg-[#145aff] text-white shadow-lg shadow-[#145aff]/20' : 'border-[#e2e4e9] bg-white text-[#020520] hover:border-[#145aff]'} ${muted ? 'opacity-40' : ''} ${past ? 'cursor-not-allowed opacity-30 hover:border-[#e2e4e9]' : ''}`}>{day.getDate()}</button>;
              })}
            </div>
            <Field label={t('posts.timeLabel')}>
              <div className="mt-4 rounded-2xl border border-[#e2e4e9] bg-[#f8faff] p-3">
                <div className="flex items-center gap-3">
                  <Clock size={18} className="text-[#145aff]" />
                  <select className={`${inputClass} bg-white font-mono`} value={selectedHour} onChange={(event) => setSelectedTime(`${event.target.value}:${selectedMinute}`)}>{hours24.map((hour) => <option key={hour} value={hour}>{hour}</option>)}</select>
                  <span className="text-lg font-bold text-[#020520]">:</span>
                  <select className={`${inputClass} bg-white font-mono`} value={selectedMinute} onChange={(event) => setSelectedTime(`${selectedHour}:${event.target.value}`)}>{minuteOptions.map((minute) => <option key={minute} value={minute}>{minute}</option>)}</select>
                  <span className="rounded-full bg-white px-3 py-2 text-xs font-semibold text-[#145aff]">Baku {BAKU_GMT_LABEL}</span>
                </div>
                {scheduleIsPast && <p className="mt-2 text-xs font-semibold text-red-600">{t('posts.pastWarning')}</p>}
              </div>
            </Field>
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-[#e2e4e9] p-4">
              <div className="flex items-center gap-2 text-lg font-semibold text-[#020520]"><ImageUp size={20} /> {t('posts.uploadTitle')}</div>
              <div className="mt-4 grid gap-3">
                <input type="file" accept="image/*,video/*" onChange={(event) => setMediaFile(event.target.files?.[0] ?? null)} className="w-full rounded-xl border border-dashed border-[#e2e4e9] bg-[#fcfcfc] px-4 py-6 text-sm text-[#696a72] file:mr-4 file:rounded-xl file:border-0 file:bg-[#145aff] file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white" />
                <input className={inputClass} placeholder={t('posts.titlePlaceholder')} value={manualTitle} onChange={(e) => setManualTitle(e.target.value)} />
                <textarea className={`${inputClass} min-h-[110px] resize-y`} placeholder={t('posts.captionPlaceholder')} value={manualCaption} onChange={(e) => setManualCaption(e.target.value)} />
                <button type="button" onClick={saveUploadedPost} disabled={savingManual || !mediaFile || !manualCaption.trim() || scheduleIsPast} className={primaryButtonClass}>{savingManual ? t('posts.saving') : t('posts.scheduleMedia')}</button>
              </div>
            </div>

            <div className="rounded-2xl border border-[#e2e4e9] p-4">
              <div className="flex items-center gap-2 text-lg font-semibold text-[#020520]"><Sparkles size={20} /> {t('posts.aiTitle')}</div>
              <div className="mt-4 grid gap-3">
                <select className={inputClass} value={productId} onChange={(e) => setProductId(e.target.value)}>
                  {productOptions.length === 0 && <option value="">{t('posts.noProducts')}</option>}
                  {productOptions.map((product) => <option key={product.id} value={product.id}>{product.title}</option>)}
                </select>
                {selectedProduct?.image_url && <img src={selectedProduct.image_url} alt={selectedProduct.title} className="h-36 w-full rounded-2xl object-cover" />}
                <textarea className={`${inputClass} min-h-[90px] resize-y`} placeholder={t('posts.promptPlaceholder')} value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)} />
                <textarea className={`${inputClass} min-h-[90px] resize-y`} placeholder={t('posts.aiCaptionPlaceholder')} value={aiCaption} onChange={(e) => setAiCaption(e.target.value)} />
                <button type="button" onClick={generateReplicateVideo} disabled={generatingVideo || !selectedProduct || !aiPrompt.trim() || !aiCaption.trim()} className={primaryButtonClass}>{generatingVideo ? <Spinner label={t('posts.generating')} /> : t('posts.generate')}</button>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={cardClass}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <span className="rounded-2xl bg-[#f0f4fe] p-3 text-[#145aff]">{activeTab === 'active' ? <CalendarDays size={22} /> : <History size={22} />}</span>
            <div>
              <h2 className="text-xl font-semibold text-[#020520]">{activeTab === 'active' ? t('posts.activeTitle') : t('posts.historyTitle')}</h2>
              <p className="mt-1 text-sm text-[#696a72]">{activeTab === 'active' ? t('posts.activeHint') : t('posts.historyHint')}</p>
            </div>
          </div>
          <div className="flex rounded-2xl border border-[#e2e4e9] bg-[#f8faff] p-1">
            <button type="button" onClick={() => setActiveTab('active')} className={`rounded-xl px-4 py-2 text-sm font-semibold ${activeTab === 'active' ? 'bg-white text-[#145aff] shadow-sm' : 'text-[#696a72]'}`}>{t('posts.activeTitle')} ({activePosts.length})</button>
            <button type="button" onClick={() => setActiveTab('history')} className={`rounded-xl px-4 py-2 text-sm font-semibold ${activeTab === 'history' ? 'bg-white text-[#145aff] shadow-sm' : 'text-[#696a72]'}`}>{t('posts.historyTitle')} ({historyPosts.length})</button>
          </div>
        </div>
        <div className="mt-5 overflow-hidden rounded-xl border border-[#e2e4e9]">
          {visiblePosts.length === 0 ? <p className="p-4 text-sm text-[#696a72]">{activeTab === 'active' ? t('posts.empty') : t('posts.historyEmpty')}</p> : (
            <div className="divide-y divide-[#e2e4e9]">
              {visiblePosts.map((post) => {
                const mediaUrl = post.media_urls[0];
                const pending = post.status === 'pending_review';
                const history = isHistoryPost(post);
                return (
                  <div key={post.id} className="grid gap-3 p-4 text-sm lg:grid-cols-[120px_96px_1fr_140px_260px] lg:items-center">
                    <span className="font-semibold capitalize text-[#020520]">{post.platform}</span>
                    <div>{mediaUrl ? (isVideoUrl(mediaUrl) ? <video src={mediaUrl} controls className="h-20 w-20 rounded-xl object-cover" /> : <img src={mediaUrl} alt={post.title ?? post.caption} className="h-20 w-20 rounded-xl object-cover" />) : <span className="text-xs text-[#696a72]">—</span>}</div>
                    <div>
                      <p className="font-semibold text-[#020520]">{post.title || post.caption.slice(0, 80)}</p>
                      <p className="text-xs text-[#696a72]">{post.media_urls.length} {t('posts.media')} · {post.scheduled_for ? formatDate(post.scheduled_for) : t('posts.noSchedule')} {post.error_message ? `· ${post.error_message}` : ''}</p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-center text-xs font-semibold ${pending ? 'bg-amber-50 text-amber-700' : 'bg-[#f5f5f5] text-[#020520]'}`}>{pending ? t('posts.pendingReview') : post.status}</span>
                    <div className="flex flex-wrap gap-2">
                      {pending ? (
                        <>
                          <button type="button" disabled={reviewingPostId === post.id || scheduleIsPast} onClick={() => approveAndSchedule(post.id)} className="inline-flex items-center justify-center gap-2 rounded-lg border border-emerald-200 px-3 py-2 text-xs font-semibold text-emerald-700 disabled:opacity-40"><CheckCircle2 size={14} /> {t('posts.approveSchedule')}</button>
                          <button type="button" disabled={reviewingPostId === post.id} onClick={() => rejectPost(post.id)} className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-xs font-semibold text-red-600 disabled:opacity-40"><XCircle size={14} /> {t('posts.reject')}</button>
                        </>
                      ) : !history ? (
                        <>
                          <button type="button" disabled={publishingPostId === post.id || post.status === 'published' || (post.status === 'scheduled' && Boolean(post.zernio_post_id))} onClick={() => publishPost(post.id)} className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#145aff] px-3 py-2 text-xs font-semibold text-[#145aff] disabled:opacity-40"><Play size={14} /> {publishingPostId === post.id ? t('posts.publishing') : post.status === 'scheduled' && post.zernio_post_id ? t('posts.scheduledButton') : t('posts.publishNow')}</button>
                          <button type="button" disabled={deletingPostId === post.id} onClick={() => deletePost(post)} className="inline-flex items-center justify-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-xs font-semibold text-red-600 disabled:opacity-40"><Trash2 size={14} /> {deletingPostId === post.id ? t('posts.deleting') : t('posts.delete')}</button>
                        </>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </motion.div>
    </section>
  );
}
