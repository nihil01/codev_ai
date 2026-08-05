import { useEffect, useState } from 'react';
import { MessageSquareReply, Save, Sparkles, Target } from 'lucide-react';

import { api } from '../../api';
import { Field } from '../../components/ui/Field';
import { cardClass, inputClass, primaryButtonClass } from '../../constants/styles';

type BotPromptSettingsProps = {
  companyId?: string | null;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

type PromptRecord = {
  title: string;
  system_prompt: string;
  version: number;
};

type PromptKind = 'bot' | 'comment' | 'intent';

type PromptEditorProps = {
  kind: PromptKind;
  eyebrow: string;
  heading: string;
  description: string;
  icon: typeof Sparkles;
  prompt: PromptRecord | null;
  loading: boolean;
  saving: boolean;
  onChange: (next: PromptRecord) => void;
  onSave: () => void;
};

function PromptEditor({
  kind,
  eyebrow,
  heading,
  description,
  icon: Icon,
  prompt,
  loading,
  saving,
  onChange,
  onSave,
}: PromptEditorProps) {
  return (
    <section className={cardClass}>
      <div className="flex items-start gap-3">
        <span className="rounded-[24px] bg-[#e4f5e9] p-3 text-[#116932]">
          <Icon size={22} />
        </span>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#15803d]">{eyebrow}</p>
          <h2 className="mt-1 text-xl font-light text-[#18261d]">{heading}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[#586b60]">{description}</p>
        </div>
      </div>

      {loading || !prompt ? (
        <p className="mt-6 text-sm text-[#586b60]">Prompt yüklənir...</p>
      ) : (
        <div className="mt-6 space-y-5">
          <Field label="Başlıq">
            <input
              id={`${kind}-prompt-title`}
              value={prompt.title}
              onChange={(event) => onChange({ ...prompt, title: event.target.value })}
              className={inputClass}
              maxLength={255}
            />
          </Field>

          <label htmlFor={`${kind}-prompt-title`} className="sr-only">{heading}</label>

          <Field label="System prompt">
            <textarea
              id={`${kind}-system-prompt`}
              value={prompt.system_prompt}
              onChange={(event) => onChange({ ...prompt, system_prompt: event.target.value })}
              className={`${inputClass} min-h-64 resize-y font-mono text-sm leading-6`}
              maxLength={20000}
            />
          </Field>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-[0.16em] text-[#708078]">
              Versiya {prompt.version}
            </span>
            <button
              type="button"
              className={primaryButtonClass}
              disabled={saving || !prompt.system_prompt.trim()}
              onClick={onSave}
            >
              <Save size={17} />
              {saving ? 'Yadda saxlanılır...' : 'Promptu yadda saxla'}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

export function BotPromptSettings({ companyId, onError, onNotice }: BotPromptSettingsProps) {
  const [botPrompt, setBotPrompt] = useState<PromptRecord | null>(null);
  const [commentPrompt, setCommentPrompt] = useState<PromptRecord | null>(null);
  const [intentPrompt, setIntentPrompt] = useState<PromptRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingKind, setSavingKind] = useState<PromptKind | null>(null);

  useEffect(() => {
    if (!companyId) {
      setBotPrompt(null);
      setCommentPrompt(null);
      setIntentPrompt(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    onError('');

    Promise.allSettled([
      api.botPrompt(companyId),
      api.commentPrompt(companyId),
      api.intentPrompt(companyId),
    ])
      .then(([botResult, commentResult, intentResult]) => {
        if (cancelled) return;
        const errors: string[] = [];

        if (botResult.status === 'fulfilled') setBotPrompt(botResult.value);
        else errors.push(botResult.reason instanceof Error ? botResult.reason.message : String(botResult.reason));

        if (commentResult.status === 'fulfilled') setCommentPrompt(commentResult.value);
        else errors.push(commentResult.reason instanceof Error ? commentResult.reason.message : String(commentResult.reason));

        if (intentResult.status === 'fulfilled') setIntentPrompt(intentResult.value);
        else errors.push(intentResult.reason instanceof Error ? intentResult.reason.message : String(intentResult.reason));

        if (errors.length > 0) onError(errors.join(' · '));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [companyId, onError]);

  async function save(kind: PromptKind) {
    if (!companyId) return;
    const current = kind === 'bot' ? botPrompt : kind === 'comment' ? commentPrompt : intentPrompt;
    if (!current?.system_prompt.trim()) return;

    setSavingKind(kind);
    onError('');
    onNotice('');
    try {
      const payload = { title: current.title.trim() || undefined, system_prompt: current.system_prompt.trim() };
      if (kind === 'bot') setBotPrompt(await api.updateBotPrompt(companyId, payload));
      else if (kind === 'comment') setCommentPrompt(await api.updateCommentPrompt(companyId, payload));
      else setIntentPrompt(await api.updateIntentPrompt(companyId, payload));
      onNotice('Prompt yadda saxlanıldı');
    } catch (error) {
      onError(error instanceof Error ? error.message : String(error));
    } finally {
      setSavingKind(null);
    }
  }

  return (
    <div className="space-y-6">
      <PromptEditor
        kind="bot"
        eyebrow="Direct və WhatsApp"
        heading="Bot system promptu"
        description="Şəxsi yazışmalardakı cavab üslubunu, məhdudiyyətləri və davranışı idarə edir."
        icon={Sparkles}
        prompt={botPrompt}
        loading={loading}
        saving={savingKind === 'bot'}
        onChange={setBotPrompt}
        onSave={() => void save('bot')}
      />
      <PromptEditor
        kind="comment"
        eyebrow="Instagram şərhləri"
        heading="Şərh system promptu"
        description="İctimai şərhlər üçün AI cavab layihələrinin tonunu və təhlükəsizlik qaydalarını idarə edir."
        icon={MessageSquareReply}
        prompt={commentPrompt}
        loading={loading}
        saving={savingKind === 'comment'}
        onChange={setCommentPrompt}
        onSave={() => void save('comment')}
      />
      <PromptEditor
        kind="intent"
        eyebrow="Dialoq analizi"
        heading="Söhbət intenti promptu"
        description="Müştərinin kurs marağını, menecerə yönləndirmə istəyini və müraciətin hazır olub-olmadığını müəyyən edən təsnifatçını idarə edir."
        icon={Target}
        prompt={intentPrompt}
        loading={loading}
        saving={savingKind === 'intent'}
        onChange={setIntentPrompt}
        onSave={() => void save('intent')}
      />
    </div>
  );
}
