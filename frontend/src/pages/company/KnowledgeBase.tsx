import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { motion } from 'framer-motion';
import { api } from '../../api';
import type { KnowledgeEntry } from '../../api';
import { cardClass, inputClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { Alert } from '../../components/ui/Alert';
import { Field } from '../../components/ui/Field';
import { Spinner } from '../../components/ui/Spinner';
import { useI18n } from '../../i18n';

type KnowledgeBaseProps = {
  companyId: string | null;
  entries: KnowledgeEntry[];
  setEntries: (entries: KnowledgeEntry[] | ((current: KnowledgeEntry[]) => KnowledgeEntry[])) => void;
  loading: boolean;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
};

function entryTypeLabel(type: KnowledgeEntry['entry_type'], t: (key: string) => string) {
  return type === 'product_photo' ? t('knowledge.photoType') : t('knowledge.textType');
}

function resolveImageUrl(imageUrl?: string | null) {
  if (!imageUrl) return '';
  return imageUrl;
}

export function KnowledgeBase({ companyId, entries, setEntries, loading, setError, setNotice }: KnowledgeBaseProps) {
  const { t } = useI18n();

  const [photoPrice, setPhotoPrice] = useState('');
  const [photoQuantity, setPhotoQuantity] = useState('');
  const [textQuantity, setTextQuantity] = useState('');
  const [photoDeliveryAvailable, setPhotoDeliveryAvailable] = useState(false);
  const [photoDescriptionLanguage, setPhotoDescriptionLanguage] = useState<'az' | 'en' | 'ru'>('az');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [photoTitle, setPhotoTitle] = useState('');
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [savingText, setSavingText] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 8;

  const sortedEntries = useMemo(
    () => [...entries].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)),
    [entries],
  );
  const totalPages = Math.max(1, Math.ceil(sortedEntries.length / pageSize));
  const pagedEntries = useMemo(
    () => sortedEntries.slice((page - 1) * pageSize, page * pageSize),
    [page, sortedEntries],
  );

  useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  async function saveTextEntry(event: FormEvent) {
    event.preventDefault();
    if (!companyId) return;

    setSavingText(true);
    setError('');
    setNotice('');

    try {
      const created = await api.createKnowledgeEntry(companyId, {
        title: title.trim(),
        content: content.trim(),
        source_url: sourceUrl.trim() || undefined,
        quantity_available: textQuantity.trim() ? Number(textQuantity) : null,
      });

      setEntries((current) => [created, ...current]);
      setPage(1);
      setTitle('');
      setContent('');
      setSourceUrl('');
      setTextQuantity('');
      setNotice(t('knowledge.saved'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingText(false);
    }
  }

  async function uploadPhoto(event: FormEvent) {
    event.preventDefault();
    if (!companyId || !photoFile) return;

    setUploadingPhoto(true);
    setError('');
    setNotice('');

    try {
      const created = await api.uploadKnowledgePhoto(
        companyId,
        photoTitle.trim() || photoFile.name,
        photoFile,
        photoPrice.trim(),
        photoQuantity.trim(),
        photoDeliveryAvailable,
        photoDescriptionLanguage,
      );

      setEntries((current) => [created, ...current]);
      setPage(1);
      setPhotoTitle('');
      setPhotoFile(null);
      setPhotoPrice('');
      setPhotoQuantity('');
      setPhotoDeliveryAvailable(false);
      setNotice(t('knowledge.photoUploaded'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploadingPhoto(false);
    }
  }

  async function deleteEntry(entryId: string) {
    if (!companyId) return;
    const confirmed = window.confirm(t('knowledge.confirmDelete'));
    if (!confirmed) return;

    setDeletingId(entryId);
    setError('');
    setNotice('');

    try {
      await api.deleteKnowledgeEntry(companyId, entryId);
      setEntries((current) => current.filter((entry) => entry.id !== entryId));
      setNotice(t('knowledge.deleted'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={`${cardClass} space-y-4`}>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#18261d]">Knowledge Base</p>
          <h2 className="mt-2 text-2xl font-light text-[#18261d]">{t('knowledge.title')}</h2>
        </div>
      </motion.div>

      <div className="grid gap-6 xl:grid-cols-2">
        <motion.form initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} onSubmit={saveTextEntry} className={`${cardClass} space-y-4`}>
          <div>
            <h3 className="text-lg font-light text-[#18261d]">{t('knowledge.addTextTitle')}</h3>
          </div>

          <Field label={t('knowledge.titleField')}>
            <input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={255} placeholder={t('knowledge.titlePlaceholder')} className={inputClass} />
          </Field>

          <Field label={t('knowledge.contentField')}>
            <textarea value={content} onChange={(event) => setContent(event.target.value)} required rows={8} maxLength={10000} placeholder={t('knowledge.contentPlaceholder')} className={`${inputClass} resize-y`} />
          </Field>

          <Field label={t('knowledge.sourceField')}>
            <input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} maxLength={2000} placeholder="https://example.com/product" className={inputClass} />
          </Field>

          <Field label={t('knowledge.quantityAvailable')}>
            <input type="number" min="0" step="1" value={textQuantity} onChange={(event) => setTextQuantity(event.target.value)} placeholder={t('knowledge.quantityPlaceholder')} className={inputClass} />
          </Field>

          <button type="submit" disabled={savingText} className={primaryButtonClass}>
            {savingText ? <Spinner label={t('knowledge.saving')} /> : t('knowledge.saveRecord')}
          </button>
        </motion.form>

        <motion.form initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} onSubmit={uploadPhoto} className={`${cardClass} space-y-4`}>
          <div>
            <h3 className="text-lg font-light text-[#18261d]">{t('knowledge.uploadTitle')}</h3>
          </div>

          <Field label={t('knowledge.productName')}>
            <input value={photoTitle} onChange={(event) => setPhotoTitle(event.target.value)} maxLength={255} placeholder={t('knowledge.productPlaceholder')} className={inputClass} />
          </Field>

          <Field label={t('knowledge.price')}>
            <div className="relative">
              <input type="number" min="0" step="0.01" value={photoPrice} onChange={(event) => setPhotoPrice(event.target.value)} placeholder={t('common.example45')} className={`${inputClass} pr-16`} />
              <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm font-semibold text-[#18261d]">AZN</span>
            </div>
          </Field>

          <Field label={t('knowledge.quantityAvailable')}>
            <input type="number" min="0" step="1" value={photoQuantity} onChange={(event) => setPhotoQuantity(event.target.value)} placeholder={t('knowledge.quantityPlaceholder')} className={inputClass} />
          </Field>

          <label className="flex cursor-pointer items-center justify-between gap-3 rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] px-4 py-3 text-sm font-semibold text-[#18261d] transition hover:border-[#15803d]">
            <span>
              <span className="block font-semibold text-[#18261d]">{t('knowledge.deliveryAvailable')}</span>
            </span>
            <input type="checkbox" checked={photoDeliveryAvailable} onChange={(event) => setPhotoDeliveryAvailable(event.currentTarget.checked)} className="h-5 w-5 rounded border-[#e1ebe4] text-[#18261d] focus:ring-[#18261d]" />
          </label>

          <Field label={t('knowledge.descriptionLanguage')}>
            <select
              value={photoDescriptionLanguage}
              onChange={(event) => setPhotoDescriptionLanguage(event.target.value as 'az' | 'en' | 'ru')}
              className={inputClass}
            >
              <option value="az">AZ</option>
              <option value="en">EN</option>
              <option value="ru">RU</option>
            </select>
          </Field>

          <Field label={t('knowledge.photo')}>
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => setPhotoFile(event.target.files?.[0] ?? null)} required className="w-full rounded-[24px] border border-dashed border-[#e1ebe4] bg-[#ffffff] px-4 py-6 text-sm text-[#18261d] outline-none transition file:mr-4 file:rounded-full file:border-0 file:bg-[#15803d] file:px-4 file:py-2 file:text-sm file:font-semibold file:text-[#ffffff] hover:border-[#15803d]" />
          </Field>

          {photoFile && <Alert type="info">{t('common.selected')}: {photoFile.name}. {t('common.maxSize')}</Alert>}

          <button type="submit" disabled={uploadingPhoto || !photoFile} className={primaryButtonClass}>
            {uploadingPhoto ? <Spinner label={t('knowledge.aiDescribe')} /> : t('knowledge.uploadAndDescribe')}
          </button>
        </motion.form>
      </div>

      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={`${cardClass} space-y-4`}>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-lg font-light text-[#18261d]">{t('knowledge.recordsTitle')}</h3>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-[#e4f5e9] px-3 py-1 text-xs font-semibold text-[#18261d]">{entries.length} {t('knowledge.recordsCount')}</span>
            {sortedEntries.length > pageSize && (
              <span className="rounded-full bg-[#e4f5e9] px-3 py-1 text-xs font-semibold text-[#18261d]">Page {page} / {totalPages}</span>
            )}
          </div>
        </div>

        {loading ? (
          <Spinner label={t('knowledge.loading')} />
        ) : sortedEntries.length === 0 ? (
          <Alert type="info">{t('knowledge.empty')}</Alert>
        ) : (
          <div className="grid gap-4">
            {pagedEntries.map((entry) => (
              <motion.article key={entry.id} layout className="rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-4 transition ">
                <div className="flex flex-col gap-4 lg:flex-row">
                  {entry.image_url && <img src={resolveImageUrl(entry.image_url)} alt={entry.title} className="h-36 w-full rounded-[24px] object-cover lg:w-44" />}
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <span className="rounded-full bg-[#e4f5e9] px-3 py-1 text-xs font-semibold text-[#18261d]">{entryTypeLabel(entry.entry_type, t)}</span>
                        <h4 className="mt-2 text-base font-light text-[#18261d]">{entry.title}</h4>
                        {entry.quantity_available !== null && entry.quantity_available !== undefined && (
                          <p className="mt-1 text-xs font-semibold uppercase tracking-[0.2em] text-[#18261d]">{t('knowledge.stock')}: {entry.quantity_available}</p>
                        )}
                      </div>
                      <button type="button" disabled={deletingId === entry.id} onClick={() => deleteEntry(entry.id)} className={secondaryButtonClass}>
                        {deletingId === entry.id ? t('common.deleting') : t('common.delete')}
                      </button>
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-[#18261d]">{entry.content}</p>
                    {entry.source_url && <a href={entry.source_url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-[#18261d] hover:opacity-80">{t('common.source')}</a>}
                  </div>
                </div>
              </motion.article>
            ))}
          </div>
        )}

        {!loading && sortedEntries.length > pageSize && (
          <div className="flex flex-col gap-3 border-t border-[#e1ebe4] pt-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-[#18261d]">
              Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, sortedEntries.length)} of {sortedEntries.length}
            </p>
            <div className="flex gap-2">
              <button type="button" className={secondaryButtonClass} disabled={page === 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</button>
              <button type="button" className={secondaryButtonClass} disabled={page === totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>Next</button>
            </div>
          </div>
        )}
      </motion.div>
    </section>
  );
}
