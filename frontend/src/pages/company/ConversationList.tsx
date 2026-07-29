import { motion } from 'framer-motion';
import type { Conversation } from '../../api';
import { cardClass } from '../../constants/styles';
import { useI18n } from '../../i18n';

type ConversationListProps = {
  conversations: Conversation[];
};

export function ConversationList({ conversations }: ConversationListProps) {
  const { t } = useI18n();

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={cardClass}>
      <h2 className="text-xl font-light text-[#18261d]">{t('conversationList.title')}</h2>

      <div className="mt-5 grid gap-3">
        {conversations.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-[#e1ebe4] bg-[#ffffff] px-4 py-8 text-center text-sm font-semibold text-[#18261d]">
            {t('conversationList.empty')}
          </div>
        ) : (
          conversations.map((conversation) => (
            <article key={conversation.id} className="rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-4 ">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-light text-[#18261d]">{conversation.customer_username || conversation.external_conversation_id}</h3>
                  <p className="mt-1 text-xs font-semibold text-[#18261d]">{conversation.status}</p>
                </div>
                <span className="rounded-full bg-[#d8e8dd] px-3 py-1 text-xs font-black text-[#18261d]">{conversation.messages.length} {t('chat.summaryMessages')}</span>
              </div>
              <p className="mt-2 line-clamp-2 text-sm text-[#18261d]">
                {conversation.messages[conversation.messages.length - 1]?.text || t('chat.noMessages')}
              </p>
            </article>
          ))
        )}
      </div>
    </motion.div>
  );
}
