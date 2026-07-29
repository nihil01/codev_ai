import { useEffect, useState } from 'react';
import { Save } from 'lucide-react';
import { api } from '../../api';
import { cardClass, inputClass, primaryButtonClass } from '../../constants/styles';
import { Spinner } from '../../components/ui/Spinner';

type Props = {
  companyId?: string | null;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

export function BotPromptSettings({ companyId, onError, onNotice }: Props) {
  const [title, setTitle] = useState('CRM prompt');
  const [prompt, setPrompt] = useState('');
  const [version, setVersion] = useState(1);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;
    setLoading(true);
    api.botPrompt(companyId)
      .then((value) => {
        if (cancelled) return;
        setTitle(value.title);
        setPrompt(value.system_prompt);
        setVersion(value.version);
      })
      .catch((error) => { if (!cancelled) onError(error instanceof Error ? error.message : String(error)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [companyId, onError]);

  async function save() {
    if (!companyId || !prompt.trim()) return;
    setSaving(true);
    onError('');
    onNotice('');
    try {
      const value = await api.updateBotPrompt(companyId, { title: title.trim() || 'CRM prompt', system_prompt: prompt.trim() });
      setTitle(value.title);
      setPrompt(value.system_prompt);
      setVersion(value.version);
      onNotice('Sistem promptu yadda saxlanıldı.');
    } catch (error) {
      onError(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className={cardClass}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#18261d]">AI assistent</p>
          <h2 className="mt-2 text-2xl font-light text-[#18261d]">Sistem promptu</h2>
          <p className="mt-2 text-sm text-[#18261d]">Botun davranışını əsas paneldən idarə edin. Cari versiya: {version}</p>
        </div>
      </div>
      {loading ? <div className="mt-5"><Spinner label="Prompt yüklənir..." /></div> : (
        <div className="mt-5 grid gap-4">
          <input className={inputClass} value={title} onChange={(event) => setTitle(event.target.value)} maxLength={255} placeholder="Prompt adı" />
          <textarea className={`${inputClass} min-h-[320px] resize-y font-mono text-sm leading-6`} value={prompt} onChange={(event) => setPrompt(event.target.value)} maxLength={3000} placeholder="Sistem promptunu daxil edin" />
          <div className="flex justify-end">
            <button type="button" className={primaryButtonClass} onClick={save} disabled={saving || !prompt.trim()}>
              <Save size={16} /> {saving ? 'Yadda saxlanılır...' : 'Promptu yadda saxla'}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
