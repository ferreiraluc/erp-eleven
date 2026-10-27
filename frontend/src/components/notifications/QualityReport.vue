<template>
  <article class="quality-report" :aria-busy="loading">
    <div class="quality-report__heading">
      <h3>{{ q('selected') }}</h3>
      <span class="quality-state" :class="`quality-state--${run.status}`">{{ q(run.status) }}</span>
    </div>
    <p class="quality-meta">
      {{ q(run.kind) }} ·
      {{ date(run.finished_at || run.started_at || run.created_at) }}
    </p>
    <p v-if="active" class="quality-notice" role="status">
      {{ q('queuedHelp') }}
    </p>
    <p v-if="run.status === 'failed'" class="quality-notice quality-warning" role="alert">
      {{ q('failed') }}
    </p>
    <section v-if="run.summary">
      <h4>{{ q('deterministic') }}</h4>
      <p class="quality-prose">{{ run.summary }}</p>
    </section>
    <section v-if="run.ai_summary" class="quality-ai">
      <h4>
        {{ q('aiSummary')
        }}<small v-if="run.provider">{{
          run.provider === 'anthropic' ? 'Claude' : 'DeepSeek'
        }}</small>
      </h4>
      <p class="quality-prose">{{ run.ai_summary }}</p>
    </section>
    <p v-else-if="!active" class="quality-muted">
      {{
        q(
          run.ai_status === 'reserved'
            ? 'aiPending'
            : ['disabled', 'budget_exhausted', 'not_requested', 'already_attempted'].includes(
                  run.ai_status || '',
                )
              ? 'aiSkipped'
              : 'aiUnavailable',
        )
      }}
    </p>
    <template v-if="!active || Object.keys(run.coverage).length">
      <p class="quality-notice" :class="{ 'quality-warning': incomplete }">
        {{ q(incomplete ? 'incomplete' : 'bounded') }}
      </p>
      <details v-if="Object.keys(run.counters).length" class="quality-counts">
        <summary>{{ q('countSummary') }}</summary>
        <dl>
          <template v-for="(count, key) in run.counters" :key="key"
            ><dt>{{ q(String(key) as QualityCopyKey) }}</dt>
            <dd>{{ count }}</dd></template
          >
        </dl>
      </details>
      <details class="quality-coverage" :open="incomplete">
        <summary>{{ q('coverage') }}</summary>
        <div class="quality-coverage__grid">
          <div
            v-for="(coverage, key) in run.coverage"
            :key="key"
            class="quality-coverage__item"
            :class="{ 'is-incomplete': !coverage.complete }"
          >
            <strong>{{ q(String(key) as QualityCopyKey) }}</strong
            ><span>{{ q('checked', { count: coverage.checked }) }}</span
            ><small>{{ q(coverage.complete ? 'withinWindow' : 'incompleteCheck') }}</small
            ><small v-if="coverage.window">{{ q(coverage.window) }}</small
            ><small v-if="coverage.comparison === 'changed_cohort_only'">{{
              q('changedCohort')
            }}</small
            ><small v-if="coverage.error">{{ q(coverage.error) }}</small>
          </div>
        </div>
        <p class="quality-muted">{{ q('bounded') }}</p>
      </details>
      <section class="quality-findings">
        <h4>{{ q('findings') }}</h4>
        <p class="quality-muted">{{ q('findingLimit') }}</p>
        <p v-if="!run.findings.length" class="quality-muted">
          {{ q('noFindings') }}
        </p>
        <ul v-else>
          <li
            v-for="(finding, index) in run.findings"
            :key="`${finding.key}:${finding.entity_id || index}`"
            :class="{ 'is-warning': finding.severity === 'warning' }"
          >
            <strong>{{ q(finding.key as QualityCopyKey) }}</strong
            ><span v-if="finding.entity_id" class="quality-reference"
              >{{ q('reference') }}: {{ finding.entity_id }}</span
            ><span v-if="finding.related_id" class="quality-reference"
              >{{ q('related') }}: {{ finding.related_id }}</span
            ><RouterLink
              v-if="qualityFindingPath(finding)"
              :to="qualityFindingPath(finding)!"
              class="erp-button erp-button--secondary erp-button--sm"
              >{{ q(finding.entity_type === 'pdv_sale' ? 'openSale' : 'open') }}
              <ArrowUpRight :size="14" aria-hidden="true"
            /></RouterLink>
          </li>
        </ul>
        <div v-if="run.findings_total > run.findings_limit" class="quality-pagination">
          <span
            >{{ run.findings_offset + 1 }}–{{
              Math.min(run.findings_offset + run.findings.length, run.findings_total)
            }}
            / {{ run.findings_total }}</span
          ><button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="loading || !run.findings_offset"
            @click="$emit('page', Math.max(0, run.findings_offset - run.findings_limit))"
          >
            {{ q('previous') }}</button
          ><button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="loading || run.findings_offset + run.findings_limit >= run.findings_total"
            @click="$emit('page', run.findings_offset + run.findings_limit)"
          >
            {{ q('next') }}
          </button>
        </div>
      </section>
    </template>
  </article>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowUpRight } from 'lucide-vue-next'
import { qualityFindingPath, type QualityRunDetail } from '@/services/systemQuality'
import { qualityText as q, type QualityCopyKey } from '@/services/systemQualityText'
import { uiLocale } from '@/i18n/uiText'
const props = defineProps<{ run: QualityRunDetail; loading?: boolean }>()
defineEmits<{ page: [offset: number] }>()
const active = computed(() => ['queued', 'running'].includes(props.run.status))
const incomplete = computed(() =>
  Object.values(props.run.coverage).some((value) => !value.complete),
)
const date = (value: string) =>
  new Date(value).toLocaleString(uiLocale(), {
    dateStyle: 'short',
    timeStyle: 'short',
  })
</script>
<style scoped>
.quality-report {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid #dbe4ef;
  border-radius: 12px;
  background: #fff;
  min-width: 0;
}
.quality-report h3,
.quality-report h4 {
  margin: 0;
  font-size: 15px;
}
.quality-report h4 {
  font-size: 13px;
  margin-bottom: 8px;
}
.quality-report__heading {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.quality-state {
  font-size: 11px;
  font-weight: 700;
  padding: 5px 8px;
  border-radius: 10px;
  background: #eff6ff;
  color: #1d4ed8;
}
.quality-state--partial,
.quality-state--failed {
  background: #fff7ed;
  color: #9a3412;
}
.quality-state--completed {
  background: #ecfdf5;
  color: #047857;
}
.quality-meta,
.quality-muted {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}
.quality-prose {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.quality-notice {
  padding: 12px;
  border-radius: 9px;
  background: #eff6ff;
  color: #1e40af;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
}
.quality-warning {
  background: #fff7ed;
  color: #9a3412;
}
.quality-ai {
  padding: 14px;
  border: 1px solid #ddd6fe;
  border-radius: 10px;
  background: #faf8ff;
}
.quality-ai h4 {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  color: #5b21b6;
}
.quality-ai small {
  font-size: 10px;
  font-weight: 500;
  border: 1px solid #ddd6fe;
  padding: 3px 6px;
  border-radius: 8px;
}
.quality-report summary {
  font-size: 13px;
  font-weight: 650;
  color: #475569;
  cursor: pointer;
}
.quality-counts dl {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px 14px;
  font-size: 12px;
  line-height: 1.5;
}
.quality-counts dt {
  color: #475569;
}
.quality-counts dd {
  margin: 0;
  font-weight: 700;
}
.quality-coverage__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 12px 0;
}
.quality-coverage__item {
  display: grid;
  gap: 5px;
  border: 1px solid #dbe4ef;
  border-radius: 10px;
  padding: 12px;
  font-size: 12px;
  background: #f8fafc;
  min-width: 0;
}
.quality-coverage__item small {
  font-size: 11px;
  line-height: 1.5;
  color: #64748b;
}
.quality-coverage__item.is-incomplete {
  border-color: #fed7aa;
  background: #fffaf5;
}
.quality-coverage__item.is-incomplete > small:first-of-type {
  color: #9a3412;
  font-weight: 650;
}
.quality-findings ul {
  list-style: none;
  margin: 12px 0;
  padding: 0;
  display: grid;
  gap: 10px;
}
.quality-findings li {
  display: grid;
  justify-items: start;
  gap: 7px;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #93c5fd;
  border-radius: 10px;
  padding: 12px;
  font-size: 13px;
  min-width: 0;
}
.quality-findings li.is-warning {
  border-left-color: #f59e0b;
}
.quality-reference {
  font-size: 11px;
  color: #64748b;
  overflow-wrap: anywhere;
}
.quality-findings a {
  text-decoration: none;
  margin-top: 3px;
}
.quality-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #64748b;
}
.quality-pagination > span {
  margin-right: auto;
}
@media (max-width: 500px) {
  .quality-report {
    padding: 12px;
  }
  .quality-coverage__grid {
    grid-template-columns: 1fr;
  }
}
</style>
