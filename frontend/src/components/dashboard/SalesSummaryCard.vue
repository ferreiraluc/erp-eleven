<template>
  <section
    class="summary-card sales-summary"
    aria-labelledby="sales-summary-title"
    :aria-busy="loading"
  >
    <header class="summary-header">
      <div class="summary-heading">
        <span class="summary-icon"><BarChart3 :size="21" aria-hidden="true" /></span>
        <div>
          <h3 id="sales-summary-title"><RouterLink to="/bi-vendas">{{auth.ownSales ? t('mySales') : t('title')}}</RouterLink></h3>
          <p>{{t('oneDriveResults')}}</p>
        </div>
      </div>
      <RouterLink :to="link('overview')" class="summary-primary"
        >{{t('openAnalysis')}} <ArrowUpRight :size="15" aria-hidden="true"
      /></RouterLink>
    </header>

    <div class="summary-body">
      <div v-if="loading" class="summary-loading" role="status">
        <RefreshCw :size="20" class="spin" aria-hidden="true" />{{t('loadingResults')}}
      </div>
      <div v-else-if="error" class="summary-error" role="alert">
        <span>{{t('summaryError')}}</span
        ><button @click="load">{{t('retry')}}</button>
      </div>
      <template v-else-if="data && latest">
        <div class="period-line">
          <span>{{ period }}</span
          ><span class="summary-badge" :class="latest.partial ? 'amber' : 'green'">{{
            latest.partial ? t('currentMonth') : t('monthlyFile')
          }}</span>
        </div>
        <div class="sales-metrics">
          <RouterLink :to="link('overview')" class="summary-metric featured"
            ><span>{{t('monthSales')}}</span><strong>{{ amount(latest.total_usd) }}</strong
            ><small
              >{{t('savedResult')}} <ArrowUpRight :size="12" aria-hidden="true" /></small
          ></RouterLink>
          <RouterLink :to="link('overview', { month: '0' })" class="summary-metric"
            ><span>{{ t('yearTotal',{year:latest.year}) }} · US$</span
            ><strong>{{ amount(annual?.total_usd) }}</strong
            ><small
              >{{ t('availableMonths',{count:annual?.available_months||0,total:annual?.source_months||0}) }} <ArrowUpRight :size="12" aria-hidden="true" /></small
          ></RouterLink>
        </div>
        <div class="sales-freshness">
          <Clock3 :size="13" aria-hidden="true" /><span
            >{{
              latest.synced_at
                ? t('dataAsOf',{date:date(latest.synced_at)})
                : t('unknownReadDate')
            }}
            {{t('syncDaily')}}</span
          >
        </div>
        <RouterLink
          v-if="
            !auth.ownSales && (latest.stale ||
            data.coverage.warnings ||
            data.selected.available_months < data.selected.source_months)
          "
          :to="link('sources')"
          class="data-warning"
          ><Info :size="14" aria-hidden="true" />{{
            latest.stale
              ? t('staleHelp')
              : t('summaryWarnings')
          }}<ArrowRight :size="13" aria-hidden="true"
        /></RouterLink>

        <div class="summary-section-heading">
          <h4>{{ t('periodHighlights',{period:shortPeriod}) }}</h4>
          <RouterLink :to="link('overview')"
            >{{auth.ownSales ? t('personalResult') : t('viewRanking')}} <ArrowRight :size="13" aria-hidden="true"
          /></RouterLink>
        </div>
        <ol v-if="data.ranking.length" class="summary-list">
          <li v-for="(seller, index) in data.ranking.slice(0, 3)" :key="seller.name">
            <RouterLink
              :to="link('overview', { seller: seller.name })"
              class="seller-row"
              :aria-label="t('sellerAria',{seller:seller.name,period})"
            >
              <span v-if="!auth.ownSales" class="seller-position" :class="{ first: index === 0 }">{{ index + 1 }}</span>
              <span class="seller-detail"
                ><span
                  ><strong>{{ seller.name }}</strong
                  ><b>US$ {{ amount(seller.total_usd) }}</b></span
                ><span class="seller-bar" aria-hidden="true"
                  ><span :style="{ width: rankWidth(seller.total_usd) + '%' }" /></span
              ></span>
              <ChevronRight :size="14" aria-hidden="true" />
            </RouterLink>
          </li>
        </ol>
        <div v-else class="summary-empty">
          <Users :size="25" aria-hidden="true" /><strong>{{t('noSellerDetail')}}</strong
          ><span>{{t('totalStillAvailable')}}</span>
        </div>
      </template>
      <div v-else class="summary-empty">
        <BarChart3 :size="28" aria-hidden="true" /><strong
          >{{t('startInExcel')}}</strong
        ><span>{{t('connectSources')}}</span
        ><RouterLink v-if="!auth.ownSales" :to="link('sources')"
          >{{t('openSources')}} <ArrowRight :size="14" aria-hidden="true"
        /></RouterLink>
      </div>
    </div>

    <footer class="summary-footer">
      <nav :aria-label="t('shortcuts')">
        <RouterLink :to="link('compare')"
          ><GitCompareArrows :size="15" aria-hidden="true" />{{t('compareYears')}}</RouterLink
        >
        <RouterLink :to="link('weeks', { month: '0' })"
          ><Trophy :size="15" aria-hidden="true" />{{t('topWeeks')}}</RouterLink
        >
        <RouterLink v-if="!auth.ownSales" :to="link('sources')"
          ><Database :size="15" aria-hidden="true" />{{t('sources')}}</RouterLink
        >
      </nav>
      <button
        class="summary-refresh"
        :disabled="loading"
        @click="load"
        :aria-label="t('reloadSummaryAria')"
        :title="t('reloadSummary')"
      >
        <RefreshCw :size="15" :class="{ spin: loading }" aria-hidden="true" />
      </button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from 'vue-i18n'
import messages from '@/components/sales/salesBi.messages.json'
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  ChevronRight,
  Clock3,
  Database,
  GitCompareArrows,
  Info,
  RefreshCw,
  Trophy,
  Users,
} from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { salesBi, type Overview } from '@/services/salesBi'

const { t, locale } = useI18n({useScope:'local',messages})
const auth = useAuthStore()
const data = ref<Overview | null>(null),
  loading = ref(true),
  error = ref(false)
const latest = computed(() =>
  data.value?.months.find(
    (m) => m.year === data.value?.latest.year && m.month === data.value?.latest.month,
  ),
)
const annual = computed(() => data.value?.annual.find((a) => a.year === latest.value?.year))
const period = computed(() =>
  latest.value
    ? new Date(latest.value.year, latest.value.month - 1, 1)
        .toLocaleDateString(locale.value, { month: 'long', year: 'numeric' })
        .replace(/^./, (letter) => letter.toUpperCase())
    : '',
)
const shortPeriod = computed(() =>
  latest.value
    ? new Date(latest.value.year, latest.value.month - 1, 1).toLocaleDateString(locale.value, {
        month: 'short',
      })
    : '',
)
const amount = (value: number | null | undefined) =>
  value == null
    ? '—'
    : value.toLocaleString(locale.value, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const date = (value: string) =>
  new Date(value).toLocaleString(locale.value, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
const rankWidth = (value: number) =>
  Math.max(0, Math.min(100, (value / Math.max(1, data.value?.ranking[0]?.total_usd || 1)) * 100))
function link(tab: string, filters: Record<string, string> = {}) {
  return {
    path: '/bi-vendas',
    query: {
      tab,
      ...(latest.value
        ? { year: String(latest.value.year), month: String(latest.value.month) }
        : {}),
      ...filters,
    },
  }
}
async function load() {
  loading.value = true
  error.value = false
  try {
    // Read the ERP snapshots only; loading the dashboard never starts a OneDrive sync.
    const initial = await salesBi.overview({})
    data.value =
      initial.latest.year && initial.latest.month
        ? await salesBi.overview({ year: initial.latest.year, month: initial.latest.month })
        : initial
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped src="./summary-card.css"></style>
<style scoped>
.sales-summary {
  --summary-accent: #047857;
  --summary-tint: #ecfdf5;
  --summary-border: #a7f3d0;
}
.period-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}
.period-line > span:first-child {
  font-size: 12px;
  color: #475569;
  font-weight: 600;
}
.sales-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.sales-metrics .summary-metric strong {
  font-size: clamp(19px, 2vw, 27px);
  letter-spacing: -0.8px;
}
.sales-metrics .featured {
  background: #ecfdf5;
  border-color: #d1fae5;
}
.sales-metrics .featured strong {
  color: #047857;
}
.sales-freshness {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  font-size: 10px;
  color: #64748b;
  padding: 10px 0;
  line-height: 1.5;
}
.sales-freshness svg {
  flex-shrink: 0;
  margin-top: 1px;
}
.data-warning {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: #92400e;
  text-decoration: none;
  padding: 7px 9px;
  background: #fffbeb;
  border-radius: 6px;
}
.data-warning svg {
  flex-shrink: 0;
}
.data-warning svg:last-child {
  margin-left: auto;
}
.seller-row {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 4px;
  text-decoration: none;
  color: #64748b;
  border-radius: 8px;
}
.seller-row:hover {
  background: #f8fafc;
}
.seller-position {
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
  width: 28px;
  height: 28px;
  border-radius: 7px;
  background: #f1f5f9;
  flex-shrink: 0;
}
.seller-position.first {
  background: #ecfdf5;
  color: #047857;
}
.seller-detail {
  flex: 1;
  min-width: 0;
}
.seller-detail > span:first-child {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: #334155;
}
.seller-detail strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.seller-detail b {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  font-weight: 600;
}
.seller-bar {
  display: block;
  height: 3px;
  background: #f1f5f9;
  margin-top: 7px;
  border-radius: 3px;
  overflow: hidden;
}
.seller-bar > span {
  display: block;
  height: 100%;
  background: #34d399;
  border-radius: 3px;
}
@media (max-width: 480px) {
  .sales-metrics .summary-metric {
    padding: 12px 9px;
  }
  .sales-metrics .summary-metric strong {
    font-size: 19px;
  }
  .sales-metrics .summary-metric > span {
    font-size: 10px;
  }
  .sales-metrics .summary-metric small {
    font-size: 9px;
  }
  .seller-detail > span:first-child {
    font-size: 11px;
    gap: 6px;
  }
}
</style>
