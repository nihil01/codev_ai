import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { CalendarDays, CheckCircle2, Clock, History, ImageUp, Play, Send, Trash2, XCircle } from 'lucide-react';
import { api } from '../../api';
import type { SocialPostDraft, SocialPostDraftCreate } from '../../api';
import { cardClass, inputClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { Field } from '../../components/ui/Field';
import { Spinner } from '../../components/ui/Spinner';
import { useI18n } from '../../i18n';

type Platform = 'instagram' | 'linkedin' | 'tiktok';
type PostsTab = 'active' | 'history';

type PostsSchedulerPanelProps = {
  companyId?: string | null;
  onError?: (message: string) => void;
  onNotice?: (message: string) => void;
};

const platformOptions: Array<{ value: Platform; label: string }> = [
  { value: 'instagram', label: 'Instagram' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'tiktok', label: 'TikTok' },
];

const BAKU_TIMEZONE = 'Asia/Baku';
const BAKU_GMT_LABEL = 'GMT+4';
const hours24 = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, '0'));
const minuteOptions = Array.from({ length: 12 }, (_, index) => String(index * 5).padStart(2, '0'));

function formatDate(value?: string | null) {
  if (!value) return '—';
  return `${new Intl.DateTimeFormat('az-AZ', { dateStyle: 'medium', timeStyle: 'short', hourCycle: 'h23', timeZone: BAKU_TIMEZONE }).format(new Date(value))} (${BAKU_GMT_LABEL})`;
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

export function PostsSchedulerPanel({ companyId, onError, onNotice }: PostsSchedulerPanelProps) {
  const { t } = useI18n();
  const initialSchedule = useMemo(() => defaultBakuSchedule(), []);
  const [posts, setPosts] = useState<SocialPostDraft[]>([]);
  const [activeTab, setActiveTab] = useState<PostsTab>('active');
  const [loading, setLoading] = useState(false);
  const [mediaFiles, setMediaFiles] = useState<File[]>([]);
  const [contentType, setContentType] = useState<'feed' | 'story' | 'reel'>('feed');
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
    if (contentType !== 'feed' && (selectedPlatforms.length !== 1 || selectedPlatforms[0] !== 'instagram')) {
      setContentType('feed');
    }
  }, [contentType, selectedPlatforms]);

  function togglePlatform(platform: Platform) {
    setSelectedPlatforms((current) => current.includes(platform) ? (current.length > 1 ? current.filter((item) => item !== platform) : current) : [...current, platform]);
  }

  async function createDraftsForPlatforms(base: Omit<SocialPostDraftCreate, 'platform'>) {
    if (!companyId) return [];
    const created: SocialPostDraft[] = [];
    try {
      for (const platform of selectedPlatforms) {
        const draft = await api.createSocialPostDraft(companyId, { ...base, platform });
        created.push(draft);
        setPosts((current) => [draft, ...current.filter((item) => item.id !== draft.id)]);
      }
      return created;
    } catch (error) {
      await Promise.allSettled(created.map((draft) => api.deleteSocialPost(companyId, draft.id)));
      const createdIds = new Set(created.map((draft) => draft.id));
      setPosts((current) => current.filter((draft) => !createdIds.has(draft.id)));
      throw error;
    }
  }

  async function saveUploadedPost() {
    if (!companyId || mediaFiles.length === 0 || !manualCaption.trim() || selectedPlatforms.length === 0) return;
    if (contentType !== 'feed' && (selectedPlatforms.length !== 1 || selectedPlatforms[0] !== 'instagram')) return onError?.('Story və Reel yalnız Instagram üçün yaradıla bilər.');
    if (contentType !== 'feed' && mediaFiles.length !== 1) return onError?.('Instagram Story və Reel üçün yalnız bir media faylı seçin.');
    if (selectedPlatforms.includes('instagram') && mediaFiles.length > 10) return onError?.('Instagram üçün maksimum 10 media faylı seçilə bilər.');
    if (selectedPlatforms.includes('tiktok') && mediaFiles.length > 35) return onError?.('TikTok üçün maksimum 35 media faylı seçilə bilər.');
    if (scheduleIsPast) return onError?.(t('posts.pastWarning'));
    setSavingManual(true); onError?.(''); onNotice?.('');
    try {
      const uploaded = await Promise.all(mediaFiles.map((file) => api.uploadSocialPostMedia(companyId, file)));
      await createDraftsForPlatforms({
        content_type: contentType,
        title: manualTitle.trim() || mediaFiles[0].name,
        caption: manualCaption.trim(),
        media_urls: uploaded.map((item) => item.url),
        scheduled_for: selectedSchedule,
        metadata: { source: 'manual_upload', filenames: uploaded.map((item) => item.filename), content_types: uploaded.map((item) => item.content_type) },
      });
      setMediaFiles([]); setContentType('feed'); setManualTitle(''); setManualCaption('');
      onNotice?.(t('posts.uploaded'));
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
      api.socialPostDrafts(companyId).then(setPosts).catch(() => undefined);
    }
    finally { setSavingManual(false); }
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

  if (loading) return <div className={cardClass}><Spinner label="Paylaşımlar yüklənir..." /></div>;

  return (
    <section className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={cardClass}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-3">
            <span className="rounded-[24px] bg-[#e4f5e9] p-3 text-[#18261d]"><Send size={22} /></span>
            <div>
              <h2 className="text-xl font-light text-[#18261d]">{t('posts.title')}</h2>
              <p className="mt-1 text-sm text-[#18261d]">{t('posts.subtitle')}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {platformOptions.map((platform) => (
              <button key={platform.value} type="button" onClick={() => togglePlatform(platform.value)} className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${selectedPlatforms.includes(platform.value) ? 'border-transparent bg-gradient-to-r from-[#15803d] to-[#4fbf73] text-white' : 'border-[#e1ebe4] bg-[#ffffff] text-[#18261d]'}`}>{platform.label}</button>
            ))}
          </div>
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[28px] border border-[#e1ebe4] bg-white p-5 shadow-sm">
            {/* Month navigation */}
            <div className="flex items-center justify-between">
              <button type="button" onClick={() => setVisibleMonth(new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() - 1, 1))}
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#e1ebe4] text-[#18261d] transition hover:bg-[#e4f5e9] hover:border-[#15803d]">←</button>
              <div className="text-center">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#15803d]">{t('posts.scheduleEyebrow')}</p>
                <h3 className="mt-1 text-xl font-bold text-[#18261d]">{new Intl.DateTimeFormat('az-AZ', { month: 'long', year: 'numeric', timeZone: BAKU_TIMEZONE }).format(visibleMonth)}</h3>
                <p className="mt-0.5 text-xs text-[#708078]">{t('posts.scheduleHint')}</p>
              </div>
              <button type="button" onClick={() => setVisibleMonth(new Date(visibleMonth.getFullYear(), visibleMonth.getMonth() + 1, 1))}
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#e1ebe4] text-[#18261d] transition hover:bg-[#e4f5e9] hover:border-[#15803d]">→</button>
            </div>

            {/* Day headers */}
            <div className="mt-5 grid grid-cols-7 gap-1.5 text-center text-[11px] font-bold uppercase tracking-wider text-[#708078]">
              {['B', 'Ç', 'Ç', 'C', 'C', 'Ş', 'B'].map((day, i) => <span key={i}>{day}</span>)}
            </div>

            {/* Calendar grid */}
            <div className="mt-2 grid grid-cols-7 gap-1.5">
              {days.map((day) => {
                const key = dateKey(day);
                const active = key === selectedDay;
                const muted = day.getMonth() !== visibleMonth.getMonth();
                const past = key < todayBakuKey();
                const isToday = key === todayBakuKey();
                return (
                  <button
                    key={key}
                    type="button"
                    disabled={past}
                    onClick={() => setSelectedDay(key)}
                    className={
                      active
                        ? 'aspect-square rounded-xl bg-[#15803d] text-white shadow-md shadow-[#15803d]/25 text-sm font-semibold transition-all'
                        : isToday
                          ? 'aspect-square rounded-xl bg-[#e4f5e9] text-[#15803d] font-bold text-sm transition-all'
                          : `aspect-square rounded-xl text-sm font-semibold text-[#18261d] hover:bg-[#f0f8f2] transition-all ${muted ? 'opacity-30' : ''} ${past ? 'cursor-not-allowed opacity-25 hover:bg-transparent' : ''}`
                    }
                  >
                    {day.getDate()}
                  </button>
                );
              })}
            </div>

            {/* Time picker */}
            <Field label={t('posts.timeLabel')}>
              <div className="mt-5 rounded-2xl border border-[#e1ebe4] bg-[#f8faf9] p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#e4f5e9] text-[#15803d]">
                    <Clock size={18} />
                  </div>
                  <select className="rounded-xl border border-[#e1ebe4] bg-white px-3 py-2.5 text-sm font-mono text-[#18261d] outline-none focus:border-[#15803d]" value={selectedHour} onChange={(event) => setSelectedTime(`${event.target.value}:${selectedMinute}`)}>
                    {hours24.map((hour) => <option key={hour} value={hour}>{hour}</option>)}
                  </select>
                  <span className="text-xl font-bold text-[#18261d]">:</span>
                  <select className="rounded-xl border border-[#e1ebe4] bg-white px-3 py-2.5 text-sm font-mono text-[#18261d] outline-none focus:border-[#15803d]" value={selectedMinute} onChange={(event) => setSelectedTime(`${selectedHour}:${event.target.value}`)}>
                    {minuteOptions.map((minute) => <option key={minute} value={minute}>{minute}</option>)}
                  </select>
                  <span className="ml-auto rounded-full border border-[#e1ebe4] bg-white px-3 py-1.5 text-xs font-semibold text-[#708078]">Baku {BAKU_GMT_LABEL}</span>
                </div>
                {scheduleIsPast && (
                  <p className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-[#116932]">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#15803d]" />
                    {t('posts.pastWarning')}
                  </p>
                )}
              </div>
            </Field>
          </div>

          <div className="space-y-4">
            <div className="rounded-[24px] border border-[#e1ebe4] p-4">
              <div className="flex items-center gap-2 text-lg font-semibold text-[#18261d]"><ImageUp size={20} /> {t('posts.uploadTitle')}</div>
              <div className="mt-4 grid gap-3">
                <label className="flex cursor-pointer items-center gap-3 rounded-[24px] border border-dashed border-[#e1ebe4] bg-white px-4 py-5 text-sm text-[#708078] transition-colors hover:border-[#15803d] hover:bg-[#e4f5e9]">
                  <input type="file" accept="image/*,video/*" multiple onChange={(event) => setMediaFiles(Array.from(event.target.files ?? []))} className="sr-only" />
                  <span className="shrink-0 rounded-full bg-[#15803d] px-4 py-2 font-medium text-white">Fayl seç</span>
                  <span className="min-w-0 truncate">{mediaFiles.length ? `${mediaFiles.length} fayl seçilib` : 'Fayl seçilməyib'}</span>
                </label>
                <select className={inputClass} value={contentType} onChange={(event) => setContentType(event.target.value as 'feed' | 'story' | 'reel')}>
                  <option value="feed">Feed / Carousel</option>
                  <option value="story" disabled={selectedPlatforms.length !== 1 || selectedPlatforms[0] !== 'instagram'}>Instagram Story</option>
                  <option value="reel" disabled={selectedPlatforms.length !== 1 || selectedPlatforms[0] !== 'instagram'}>Instagram Reel</option>
                </select>
                <input className={inputClass} placeholder={t('posts.titlePlaceholder')} value={manualTitle} onChange={(e) => setManualTitle(e.target.value)} />
                <textarea className={`${inputClass} min-h-[110px] resize-y`} placeholder={t('posts.captionPlaceholder')} value={manualCaption} onChange={(e) => setManualCaption(e.target.value)} />
                <button type="button" onClick={saveUploadedPost} disabled={savingManual || mediaFiles.length === 0 || !manualCaption.trim() || scheduleIsPast} className={primaryButtonClass}>{savingManual ? t('posts.saving') : t('posts.scheduleMedia')}</button>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={cardClass}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <span className="rounded-[24px] bg-[#e4f5e9] p-3 text-[#18261d]">{activeTab === 'active' ? <CalendarDays size={22} /> : <History size={22} />}</span>
            <div>
              <h2 className="text-xl font-light text-[#18261d]">{activeTab === 'active' ? t('posts.activeTitle') : t('posts.historyTitle')}</h2>
              <p className="mt-1 text-sm text-[#18261d]">{activeTab === 'active' ? t('posts.activeHint') : t('posts.historyHint')}</p>
            </div>
          </div>
          <div className="flex rounded-[24px] border border-[#e1ebe4] bg-[#e4f5e9] p-1">
            <button type="button" onClick={() => setActiveTab('active')} className={`rounded-[24px] px-4 py-2 text-sm font-semibold ${activeTab === 'active' ? 'bg-[#ffffff] text-[#18261d] ' : 'text-[#18261d]'}`}>{t('posts.activeTitle')} ({activePosts.length})</button>
            <button type="button" onClick={() => setActiveTab('history')} className={`rounded-[24px] px-4 py-2 text-sm font-semibold ${activeTab === 'history' ? 'bg-[#ffffff] text-[#18261d] ' : 'text-[#18261d]'}`}>{t('posts.historyTitle')} ({historyPosts.length})</button>
          </div>
        </div>
        <div className="mt-5 overflow-hidden rounded-[24px] border border-[#e1ebe4]">
          {visiblePosts.length === 0 ? <p className="p-4 text-sm text-[#18261d]">{activeTab === 'active' ? t('posts.empty') : t('posts.historyEmpty')}</p> : (
            <div className="divide-y divide-[#e1ebe4]">
              {visiblePosts.map((post) => {
                const mediaUrl = post.media_urls[0];
                const pending = post.status === 'pending_review';
                const history = isHistoryPost(post);
                return (
                  <div key={post.id} className="grid gap-3 p-4 text-sm lg:grid-cols-[120px_96px_1fr_140px_260px] lg:items-center">
                    <span className="font-semibold capitalize text-[#18261d]">{post.platform}</span>
                    <div>{mediaUrl ? (isVideoUrl(mediaUrl) ? <video src={mediaUrl} controls className="h-20 w-20 rounded-[24px] object-cover" /> : <img src={mediaUrl} alt={post.title ?? post.caption} className="h-20 w-20 rounded-[24px] object-cover" />) : <span className="text-xs text-[#18261d]">—</span>}</div>
                    <div>
                      <p className="font-semibold text-[#18261d]">{post.title || post.caption.slice(0, 80)}</p>
                      <p className="text-xs text-[#18261d]">{post.media_urls.length} {t('posts.media')} · {post.scheduled_for ? formatDate(post.scheduled_for) : t('posts.noSchedule')} {post.error_message ? `· ${post.error_message}` : ''}</p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-center text-xs font-semibold ${pending ? 'bg-[#ffffff] text-[#18261d]' : 'bg-[#e4f5e9] text-[#18261d]'}`}>{pending ? t('posts.pendingReview') : post.status}</span>
                    <div className="flex flex-wrap gap-2">
                      {pending ? (
                        <>
                          <button type="button" disabled={reviewingPostId === post.id || scheduleIsPast} onClick={() => approveAndSchedule(post.id)} className="inline-flex items-center justify-center gap-2 rounded-[24px] border border-[#ffffff] px-3 py-2 text-xs font-semibold text-[#18261d] disabled:opacity-40"><CheckCircle2 size={14} /> {t('posts.approveSchedule')}</button>
                          <button type="button" disabled={reviewingPostId === post.id} onClick={() => rejectPost(post.id)} className="inline-flex items-center justify-center gap-2 rounded-[24px] border border-[#d8e8dd] px-3 py-2 text-xs font-semibold text-[#116932] disabled:opacity-40"><XCircle size={14} /> {t('posts.reject')}</button>
                        </>
                      ) : !history ? (
                        <>
                          <button type="button" disabled={publishingPostId === post.id || post.status === 'published' || (post.status === 'scheduled' && Boolean(post.zernio_post_id))} onClick={() => publishPost(post.id)} className="inline-flex items-center justify-center gap-2 rounded-[24px] border border-[#18261d] px-3 py-2 text-xs font-semibold text-[#18261d] disabled:opacity-40"><Play size={14} /> {publishingPostId === post.id ? t('posts.publishing') : post.status === 'scheduled' && post.zernio_post_id ? t('posts.scheduledButton') : t('posts.publishNow')}</button>
                          <button type="button" disabled={deletingPostId === post.id} onClick={() => deletePost(post)} className="inline-flex items-center justify-center gap-2 rounded-[24px] border border-[#d8e8dd] px-3 py-2 text-xs font-semibold text-[#116932] disabled:opacity-40"><Trash2 size={14} /> {deletingPostId === post.id ? t('posts.deleting') : t('posts.delete')}</button>
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
