import { ContactsPanel } from './ContactsPanel';

type ContactsWorkspaceProps = {
  companyId: string | null | undefined;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
  onAnalyticsChange?: () => void | Promise<void>;
};

export function ContactsWorkspace({
  companyId,
  onError,
  onNotice,
}: ContactsWorkspaceProps) {
  return (
    <section className="space-y-5">
      <ContactsPanel companyId={companyId} onError={onError} onNotice={onNotice} />
    </section>
  );
}
