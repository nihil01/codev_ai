import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { animate, motion, useMotionValue, useTransform } from 'framer-motion';
import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  CalendarDays,
  MessageCircle,
  MessagesSquare,
  RefreshCw,
  Send,
  Sparkles,
  Users,
} from 'lucide-react';
import { api, type MessageActivity, type MessageActivityCustomer } from '../../api';
import { InstagramIcon } from '../ui/SocialIcons';

const BAKU_TIME_ZONE = 'Asia/Baku';

const COLORS = {
  ink: '#18261d',
  green: '#15803d',
  mint: '#86efac',
  pale: '#e4f5e9',
  line: '#d8e8dd',
  white: '#ffffff',
};

const EMPTY_ACTIVITY: MessageActivity = {
  tenant_id: '',
  date_from: '',
  date_to: '',
  total_messages: 0,
  inbound_messages: 0,
  outbound_messages: 0,
  active_customers: 0,
  today_messages: 0,
  today_customers_count: 0,
  daily_activity: [],
  channel_activity: [],
  top_customers: [],
  today_customers: [],
};

type Props = {
  companyId: string | null;
  igActivated: boolean;
  wpActivated: boolean;
};

function bakuDate(date: Date): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: BAKU_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? '';
  return `${value('year')}-${value('month')}-${value('day')}`;
}

function shiftDate(value: string, days: number): string {
  const [year, month, day] = value.split('-').map(Number);
  const shifted = new Date(Date.UTC(year, month - 1, day));
  shifted.setUTCDate(shifted.getUTCDate() + days);
  return shifted.toISOString().slice(0, 10);
}

function defaultRange(): { from: string; to: string } {
  const to = bakuDate(new Date());
  return { from: shiftDate(to, -13), to };
}

function shortDate(value: string): string {
  const [, month, day] = value.split('-');
  return `${day}.${month}`;
}

function formatLastSeen(value?: string | null): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('az-AZ', {
    timeZone: BAKU_TIME_ZONE,
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

export function DashboardOverview({ companyId, igActivated, wpActivated }: Props) {
  const initialRange = useMemo(defaultRange, []);
  const [dateFrom, setDateFrom] = useState(initialRange.from);
  const [dateTo, setDateTo] = useState(initialRange.to);
  const [activity, setActivity] = useState<MessageActivity>(EMPTY_ACTIVITY);
  const [loading, setLoading] = useState(Boolean(companyId));
  const [error, setError] = useState('');
  const requestGeneration = useRef(0);
  const requestController = useRef<AbortController | null>(null);

  useLayoutEffect(() => {
    ++requestGeneration.current;
    requestController.current?.abort();
    requestController.current = null;
    setActivity(EMPTY_ACTIVITY);
    setError('');
    setLoading(Boolean(companyId));
  }, [companyId]);

  async function loadData() {
    const generation = ++requestGeneration.current;
    requestController.current?.abort();
    if (!companyId) {
      requestController.current = null;
      setActivity(EMPTY_ACTIVITY);
      setError('');
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    requestController.current = controller;
    setActivity(EMPTY_ACTIVITY);
    setLoading(true);
    setError('');
    try {
      const result = await api.messageActivity(companyId, { from: dateFrom, to: dateTo }, controller.signal);
      if (generation === requestGeneration.current) setActivity(result);
    } catch (loadError) {
      if (generation === requestGeneration.current && !controller.signal.aborted) {
        setActivity(EMPTY_ACTIVITY);
        setError(loadError instanceof Error ? loadError.message : String(loadError));
      }
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
    return () => requestController.current?.abort();
  }, [companyId, dateFrom, dateTo]);

  const dailyData = useMemo(
    () => activity.daily_activity.map((item) => ({
      ...item,
      label: shortDate(item.date),
      total: item.inbound + item.outbound,
    })),
    [activity.daily_activity],
  );

  const channelData = useMemo(
    () => activity.channel_activity.map((item) => ({
      ...item,
      name: item.channel === 'instagram' ? 'Instagram' : 'WhatsApp',
      value: item.inbound + item.outbound,
    })),
    [activity.channel_activity],
  );

  const responseRatio = activity.inbound_messages > 0
    ? Math.min(Math.round((activity.outbound_messages / activity.inbound_messages) * 100), 100)
    : 0;

  return (
    <section className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-[28px] border border-[#d8e8dd] bg-[#18261d] px-6 py-6 text-white md:px-8"
      >
        <div className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-[#15803d]/40 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-1/3 h-24 w-72 rounded-full bg-[#86efac]/10 blur-2xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1.5 text-xs font-semibold text-[#bbf7d0]">
              <Sparkles size={14} /> Canlı mesaj analitikası
            </div>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight text-white md:text-3xl">Müştəri aktivliyi</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-white/65">
              Gündəlik yazışmaları, bu gün aktiv olan müştəriləri və ən çox mesaj yazanları izləyin.
            </p>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <DateField label="Başlanğıc" value={dateFrom} max={dateTo} onChange={setDateFrom} />
            <DateField label="Son" value={dateTo} min={dateFrom} onChange={setDateTo} />
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={loading || !companyId}
              className="inline-flex h-[42px] items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 text-xs font-semibold text-white transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
              Yenilə
            </button>
          </div>
        </div>
      </motion.div>

      {loading ? (
        <DashboardSkeleton />
      ) : error ? (
        <div className="rounded-[20px] border border-red-200 bg-red-50 px-4 py-6 text-sm text-red-700" role="alert">
          Məlumatları yükləmək mümkün olmadı: {error}
        </div>
      ) : (
        <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          delay={0}
          icon={<MessagesSquare size={20} />}
          label="Seçilmiş dövrdə mesajlar"
          value={activity.total_messages}
          helper={`${activity.inbound_messages} daxil olan · ${activity.outbound_messages} göndərilən`}
        />
        <MetricCard
          delay={0.05}
          icon={<MessageCircle size={20} />}
          label="Bu gün yazılan mesajlar"
          value={activity.today_messages}
          helper={`${activity.today_customers_count} aktiv müştəri`}
          accent
        />
        <MetricCard
          delay={0.1}
          icon={<Users size={20} />}
          label="Aktiv müştərilər"
          value={activity.active_customers}
          helper="Seçilmiş tarix aralığında"
        />
        <MetricCard
          delay={0.15}
          icon={<Send size={20} />}
          label="Cavab aktivliyi"
          value={responseRatio}
          suffix="%"
          helper="Göndərilən / daxil olan mesajlar"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <ChartCard
          className="xl:col-span-8"
          title="Mesajların gündəlik dinamikası"
          subtitle="Daxil olan və göndərilən mesajların günlər üzrə dəyişimi"
        >
          <div className="h-[310px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailyData} margin={{ top: 16, right: 8, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="inboundArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COLORS.green} stopOpacity={0.4} />
                    <stop offset="100%" stopColor={COLORS.green} stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="outboundArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COLORS.ink} stopOpacity={0.24} />
                    <stop offset="100%" stopColor={COLORS.ink} stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={COLORS.line} strokeDasharray="4 6" vertical={false} />
                <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#617066', fontSize: 11 }} />
                <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#617066', fontSize: 11 }} />
                <Tooltip content={<ActivityTooltip />} />
                <Area
                  type="monotone"
                  dataKey="inbound"
                  name="Daxil olan"
                  stroke={COLORS.green}
                  strokeWidth={3}
                  fill="url(#inboundArea)"
                  animationDuration={900}
                />
                <Area
                  type="monotone"
                  dataKey="outbound"
                  name="Göndərilən"
                  stroke={COLORS.ink}
                  strokeWidth={2}
                  fill="url(#outboundArea)"
                  animationDuration={1100}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <ChartLegend />
        </ChartCard>

        <ChartCard
          className="xl:col-span-4"
          title="Kanallar üzrə aktivlik"
          subtitle="Instagram və WhatsApp mesajlarının payı"
        >
          <div className="relative h-[230px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={channelData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={68}
                  outerRadius={92}
                  paddingAngle={5}
                  cornerRadius={8}
                  animationDuration={900}
                >
                  {channelData.map((entry) => (
                    <Cell key={entry.channel} fill={entry.channel === 'instagram' ? COLORS.green : COLORS.ink} />
                  ))}
                </Pie>
                <Tooltip content={<ChannelTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <AnimatedNumber className="text-3xl font-semibold text-[#18261d]" value={activity.total_messages} />
              <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#617066]">mesaj</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <ChannelPill
              active={igActivated}
              color={COLORS.green}
              label="Instagram"
              value={channelData.find((item) => item.channel === 'instagram')?.value ?? 0}
            />
            <ChannelPill
              active={wpActivated}
              color={COLORS.ink}
              label="WhatsApp"
              value={channelData.find((item) => item.channel === 'whatsapp')?.value ?? 0}
            />
          </div>
        </ChartCard>
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <ChartCard
          className="xl:col-span-7"
          title="Günlük müştəri axını"
          subtitle="Hər gün yazan unikal müştərilər və ümumi mesaj sayı"
        >
          <div className="h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={dailyData} margin={{ top: 16, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid stroke={COLORS.line} strokeDasharray="4 6" vertical={false} />
                <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#617066', fontSize: 11 }} />
                <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#617066', fontSize: 11 }} />
                <Tooltip content={<ActivityTooltip />} />
                <Bar
                  dataKey="active_customers"
                  name="Aktiv müştərilər"
                  fill={COLORS.mint}
                  radius={[8, 8, 3, 3]}
                  maxBarSize={30}
                  animationDuration={800}
                />
                <Line
                  type="monotone"
                  dataKey="total"
                  name="Ümumi mesaj"
                  stroke={COLORS.ink}
                  strokeWidth={3}
                  dot={{ r: 3, fill: COLORS.white, stroke: COLORS.ink, strokeWidth: 2 }}
                  activeDot={{ r: 5, fill: COLORS.green, stroke: COLORS.white, strokeWidth: 2 }}
                  animationDuration={1100}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>

        <CustomerList
          className="xl:col-span-5"
          title="Bu gün kim yazıb?"
          subtitle={`${activity.today_customers_count} müştəri bu gün aktiv olub`}
          customers={activity.today_customers}
          countKey="today_message_count"
          emptyText="Bu gün hələ daxil olan mesaj yoxdur."
          today
        />
      </div>

      <CustomerRanking customers={activity.top_customers} />
        </>
      )}
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" aria-label="Mesaj aktivliyi yüklənir" aria-busy="true">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="h-32 animate-pulse rounded-[24px] border border-[#d8e8dd] bg-[#eef6f0]" />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-12">
        <div className="h-[380px] animate-pulse rounded-[28px] border border-[#d8e8dd] bg-[#eef6f0] xl:col-span-8" />
        <div className="h-[380px] animate-pulse rounded-[28px] border border-[#d8e8dd] bg-[#eef6f0] xl:col-span-4" />
      </div>
    </div>
  );
}

function DateField({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: string;
  min?: string;
  max?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/55">
      {label}
      <span className="relative">
        <CalendarDays className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/60" size={14} />
        <input
          type="date"
          value={value}
          min={min}
          max={max}
          onChange={(event) => onChange(event.target.value)}
          className="h-[42px] rounded-full border border-white/15 bg-white/10 pl-9 pr-3 text-xs font-semibold normal-case tracking-normal text-white outline-none transition focus:border-[#86efac] [color-scheme:dark]"
        />
      </span>
    </label>
  );
}

function AnimatedNumber({ value, suffix = '', className = '' }: { value: number; suffix?: string; className?: string }) {
  const motionValue = useMotionValue(0);
  const rounded = useTransform(motionValue, (latest) => `${Math.round(latest).toLocaleString('az-AZ')}${suffix}`);

  useEffect(() => {
    const controls = animate(motionValue, value, { duration: 0.75, ease: 'easeOut' });
    return controls.stop;
  }, [motionValue, value]);

  return <motion.span className={className}>{rounded}</motion.span>;
}

function MetricCard({
  icon,
  label,
  value,
  helper,
  suffix,
  delay,
  accent = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  helper: string;
  suffix?: string;
  delay: number;
  accent?: boolean;
}) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay, duration: 0.4 }}
      whileHover={{ y: -3 }}
      className={`relative overflow-hidden rounded-[24px] border p-5 ${
        accent ? 'border-[#bbf7d0] bg-[#e4f5e9]' : 'border-[#d8e8dd] bg-white'
      }`}
    >
      <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-[#86efac]/20 blur-2xl" />
      <div className="relative flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#617066]">{label}</p>
          <AnimatedNumber className="mt-3 block text-3xl font-semibold tracking-tight text-[#18261d]" value={value} suffix={suffix} />
          <p className="mt-2 text-xs text-[#617066]">{helper}</p>
        </div>
        <span className="rounded-2xl bg-[#18261d] p-2.5 text-[#86efac]">{icon}</span>
      </div>
    </motion.article>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
  className = '',
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.article
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className={`rounded-[28px] border border-[#d8e8dd] bg-white p-5 md:p-6 ${className}`}
    >
      <h2 className="text-lg font-semibold text-[#18261d]">{title}</h2>
      <p className="mt-1 text-xs leading-5 text-[#617066]">{subtitle}</p>
      <div className="mt-5">{children}</div>
    </motion.article>
  );
}

function ChartLegend() {
  return (
    <div className="mt-2 flex flex-wrap gap-4 text-xs font-medium text-[#617066]">
      <span className="inline-flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-full bg-[#15803d]" />Daxil olan</span>
      <span className="inline-flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-full bg-[#18261d]" />Göndərilən</span>
    </div>
  );
}

function ActivityTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-2xl border border-[#d8e8dd] bg-white/95 px-4 py-3 text-xs backdrop-blur">
      <p className="mb-2 font-semibold text-[#18261d]">{label}</p>
      {payload.map((item: any) => (
        <p key={item.dataKey} className="mt-1 flex items-center justify-between gap-6 text-[#617066]">
          <span>{item.name}</span><strong style={{ color: item.color }}>{item.value}</strong>
        </p>
      ))}
    </div>
  );
}

function ChannelTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="rounded-2xl border border-[#d8e8dd] bg-white px-4 py-3 text-xs">
      <p className="font-semibold text-[#18261d]">{item.name}</p>
      <p className="mt-1 text-[#617066]">{item.value} mesaj</p>
    </div>
  );
}

function ChannelPill({ active, color, label, value }: { active: boolean; color: string; label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-[#d8e8dd] bg-[#f8fbf9] px-3 py-3">
      <div className="flex items-center gap-2 text-xs font-semibold text-[#18261d]">
        <i className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
        {label}
      </div>
      <p className="mt-2 text-lg font-semibold text-[#18261d]">{value}</p>
      <p className="text-[10px] text-[#617066]">{active ? 'Qoşulub' : 'Qoşulmayıb'}</p>
    </div>
  );
}

function CustomerAvatar({ customer }: { customer: MessageActivityCustomer }) {
  const initial = customer.customer_label.trim().charAt(0).toUpperCase() || '?';
  return (
    <span className="relative grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-[#18261d] text-sm font-semibold text-[#86efac]">
      {initial}
      <i className="absolute -bottom-1 -right-1 grid h-5 w-5 place-items-center rounded-full border-2 border-white bg-[#e4f5e9] text-[#15803d]">
        {customer.channel === 'instagram' ? <InstagramIcon size={10} /> : <MessageCircle size={10} />}
      </i>
    </span>
  );
}

function CustomerList({
  title,
  subtitle,
  customers,
  countKey,
  emptyText,
  className = '',
}: {
  title: string;
  subtitle: string;
  customers: MessageActivityCustomer[];
  countKey: 'message_count' | 'today_message_count';
  emptyText: string;
  className?: string;
  today?: boolean;
}) {
  return (
    <ChartCard className={className} title={title} subtitle={subtitle}>
      {customers.length === 0 ? (
        <div className="grid min-h-[220px] place-items-center rounded-[22px] border border-dashed border-[#d8e8dd] bg-[#f8fbf9] px-6 text-center">
          <div>
            <MessageCircle className="mx-auto text-[#86a18e]" size={28} />
            <p className="mt-3 text-sm text-[#617066]">{emptyText}</p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {customers.slice(0, 6).map((customer, index) => (
            <motion.div
              key={`${customer.channel}-${customer.customer_id}`}
              initial={{ opacity: 0, x: 14 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              className="flex items-center gap-3 rounded-[20px] border border-[#e7efe9] bg-[#f8fbf9] px-3 py-3"
            >
              <CustomerAvatar customer={customer} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-[#18261d]">{customer.customer_label}</p>
                <p className="mt-0.5 text-[10px] text-[#617066]">Son mesaj: {formatLastSeen(customer.last_message_at)}</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-semibold text-[#15803d]">{customer[countKey]}</p>
                <p className="text-[9px] uppercase tracking-wide text-[#617066]">mesaj</p>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </ChartCard>
  );
}

function CustomerRanking({ customers }: { customers: MessageActivityCustomer[] }) {
  const max = Math.max(...customers.map((customer) => customer.message_count), 1);
  return (
    <ChartCard title="Ən aktiv müştərilər" subtitle="Seçilmiş dövrdə ən çox daxil olan mesaj yazan müştərilər">
      {customers.length === 0 ? (
        <div className="rounded-[22px] border border-dashed border-[#d8e8dd] bg-[#f8fbf9] px-6 py-12 text-center text-sm text-[#617066]">
          Seçilmiş dövr üçün müştəri mesajı tapılmadı.
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {customers.map((customer, index) => (
            <motion.div
              key={`${customer.channel}-${customer.customer_id}`}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.04 }}
              className="rounded-[22px] border border-[#e7efe9] bg-[#f8fbf9] p-4"
            >
              <div className="flex items-center gap-3">
                <span className="text-xs font-bold text-[#86a18e]">#{index + 1}</span>
                <CustomerAvatar customer={customer} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-[#18261d]">{customer.customer_label}</p>
                  <p className="text-[10px] capitalize text-[#617066]">{customer.channel}</p>
                </div>
                <strong className="text-xl text-[#18261d]">{customer.message_count}</strong>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#d8e8dd]">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.max((customer.message_count / max) * 100, 4)}%` }}
                  transition={{ duration: 0.7, delay: 0.1 + index * 0.04 }}
                  className="h-full rounded-full bg-gradient-to-r from-[#15803d] to-[#86efac]"
                />
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </ChartCard>
  );
}
