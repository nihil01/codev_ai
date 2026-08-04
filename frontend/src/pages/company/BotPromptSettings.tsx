import { useEffect, useState } from 'react';
import { MessageCircle, MessagesSquare, Save } from 'lucide-react';
import { api } from '../../api';
import { cardClass, inputClass, primaryButtonClass } from '../../constants/styles';
import { Spinner } from '../../components/ui/Spinner';

type Props = { companyId?: string | null; onError: (message: string) => void; onNotice: (message: string) => void };
type PromptState = { title: string; system_prompt: string; version: number };
const empty: PromptState = { title: '', system_prompt: '', version: 1 };

export function BotPromptSettings({ companyId, onError, onNotice }: Props) {
  const [direct, setDirect] = useState<PromptState>(empty);
  const [comments, setComments] = useState<PromptState>(empty);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState<'direct' | 'comments' | null>(null);

  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([api.botPrompt(companyId), api.commentPrompt(companyId)])
      .then(([directResult, commentResult]) => {
        if (cancelled) return;
        const failures: string[] = [];
        if (directResult.status === 'fulfilled') setDirect(directResult.value);
        else failures.push(`Mesaj promptu: ${directResult.reason instanceof Error ? directResult.reason.message : String(directResult.reason)}`);
        if (commentResult.status === 'fulfilled') setComments(commentResult.value);
        else failures.push(`Şərh promptu: ${commentResult.reason instanceof Error ? commentResult.reason.message : String(commentResult.reason)}`);
        if (failures.length) onError(failures.join(' · '));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [companyId, onError]);

  async function save(kind: 'direct' | 'comments') {
    if (!companyId) return;
    const state = kind === 'direct' ? direct : comments;
    if (!state.system_prompt.trim()) return;
    setSaving(kind);
    onError('');
    onNotice('');
    try {
      const value = kind === 'direct'
        ? await api.updateBotPrompt(companyId, { title: state.title.trim() || 'Codev satış assistenti', system_prompt: state.system_prompt.trim() })
        : await api.updateCommentPrompt(companyId, { title: state.title.trim() || 'Instagram şərh assistenti', system_prompt: state.system_prompt.trim() });
      if (kind === 'direct') setDirect(value); else setComments(value);
      onNotice(`${kind === 'direct' ? 'Mesaj' : 'Şərh'} promptu yadda saxlanıldı.`);
    } catch (error) {
      onError(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(null);
    }
  }

  const editor = (kind: 'direct' | 'comments', value: PromptState, setValue: (next: PromptState) => void) => (
    <article className={cardClass}>
      <div className="flex items-center gap-3">
        <span className="grid h-11 w-11 place-items-center rounded-full bg-[#e4f5e9] text-[#15803d]">{kind === 'direct' ? <MessagesSquare size={20} /> : <MessageCircle size={20} />}</span>
        <div><h3 className="text-lg font-semibold text-[#18261d]">{kind === 'direct' ? 'Direct və WhatsApp promptu' : 'Instagram şərh promptu'}</h3><p className="text-xs text-[#708078]">Cari versiya: {value.version}</p></div>
      </div>
      <div className="mt-5 grid gap-4">
        <label htmlFor={`${kind}-prompt-title`} className="text-sm font-semibold text-[#18261d]">Prompt adı</label>
        <input id={`${kind}-prompt-title`} className={inputClass} value={value.title} onChange={(event) => setValue({ ...value, title: event.target.value })} maxLength={255} />
        <label htmlFor={`${kind}-system-prompt`} className="text-sm font-semibold text-[#18261d]">Sistem promptu</label>
        <textarea id={`${kind}-system-prompt`} className={`${inputClass} min-h-[360px] resize-y font-mono text-sm leading-6`} value={value.system_prompt} onChange={(event) => setValue({ ...value, system_prompt: event.target.value })} maxLength={20000} />
        <div className="flex justify-end"><button type="button" className={primaryButtonClass} onClick={() => save(kind)} disabled={saving !== null || !value.system_prompt.trim()}><Save size={16} /> {saving === kind ? 'Yadda saxlanılır...' : 'Promptu yadda saxla'}</button></div>
      </div>
    </article>
  );

  if (loading) return <div className={cardClass}><Spinner label="Promptlar yüklənir..." /></div>;
  return <section className="space-y-5"><div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#15803d]">AI assistent</p><h2 className="mt-1 text-2xl font-semibold text-[#18261d]">Runtime promptları</h2><p className="mt-2 text-sm text-[#708078]">Codev botunun mesaj və şərh davranışını ayrıca idarə edin.</p></div>{editor('direct', direct, setDirect)}{editor('comments', comments, setComments)}</section>;
}
