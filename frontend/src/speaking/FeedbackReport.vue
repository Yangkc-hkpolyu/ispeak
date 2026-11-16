<!-- Section navigation and answer accordion adapted from PolyInterview feedback components. -->
<template>
  <section class="assessment-report" aria-label="Speaking assessment">
    <p v-if="loading" role="status">Loading your saved assessment...</p>
    <div v-if="error" role="alert" class="notice">{{ error }} <button class="text-button" @click="load">Try again</button></div>
    <template v-if="data">
      <p class="assessment-scope">{{ data.scope }}</p>
      <p v-if="data.coverage.early_finish" class="notice">You finished early. This report covers only the answers submitted.</p>
      <p v-if="data.source==='offline_demo'" class="notice">Offline walkthrough: no AI scores were generated.</p>
      <nav class="assessment-tabs" aria-label="Assessment sections">
        <button :class="{active:active==='overview'}" :aria-pressed="active==='overview'" @click="active='overview'">Overview</button>
        <button :class="{active:active==='answers'}" :aria-pressed="active==='answers'" @click="active='answers'">Answer review ({{ data.questions.length }})</button>
      </nav>
      <section v-show="active==='overview'||printing" aria-label="Performance overview">
        <p class="assessment-summary">{{ data.summary }}</p>
        <div class="assessment-overview">
          <radar-chart :items="data.dimensions" />
          <div class="assessment-dimensions"><article v-for="item in data.dimensions" :key="item.key"><header><h3>{{ item.label }}</h3><strong>{{ scoreText(item.score) }}</strong></header><div v-if="valid(item.score)" class="assessment-track"><i :style="{width:item.score*10+'%'}"></i></div><p>{{ item.comment || 'There is not enough reliable evidence to assess this dimension.' }}</p></article></div>
        </div>
        <div class="assessment-advice"><section v-if="data.strengths.length"><h3>What went well</h3><ul><li v-for="item in data.strengths" :key="item">{{ item }}</li></ul></section><section v-if="data.improvements.length"><h3>What to improve</h3><ul><li v-for="item in data.improvements" :key="item">{{ item }}</li></ul></section></div>
        <section v-if="data.next_steps.length" class="assessment-next"><h3>Your next practice steps</h3><ol><li v-for="item in data.next_steps" :key="item">{{ item }}</li></ol></section>
      </section>
      <section v-show="active==='answers'||printing" aria-label="Question-by-question feedback">
        <div class="answer-review-heading"><h3>Feedback for each answer</h3><button class="text-button" @click="expanded=!expanded">{{ expanded?'Collapse answers':'Expand all answers' }}</button></div>
        <details v-for="question in data.questions" :key="question.id || question.number" :open="expanded||printing||question.number===1" class="assessment-answer">
          <summary><span class="answer-number">{{ question.number }}</span><span>{{ question.question }}</span><small>{{ statusText(question.status) }}</small></summary>
          <div class="answer-body">
            <p class="answer-stage">{{ question.stage.replace(/_/g,' ') }}</p>
            <div class="answer-comparison"><article><h4>Your answer</h4><p>{{ question.answer || 'No answer was captured.' }}</p></article><article v-if="question.corrections.length"><h4>Suggested revision</h4><p>{{ question.revised_answer }}</p></article></div>
            <div class="answer-dimensions"><div v-for="item in question.dimensions" :key="item.key"><span>{{ item.label }}</span><strong>{{ scoreText(item.score) }}</strong><p>{{ item.comment }}</p></div></div>
            <section v-if="question.corrections.length"><h4>What changed and why</h4><article v-for="(correction,index) in question.corrections" :key="index" class="answer-correction"><p><del>{{ correction.original }}</del><br><ins>{{ correction.revised }}</ins></p><p>{{ correction.reason }}</p></article></section>
            <details class="answer-evidence"><summary>Assessment evidence and suggestions</summary><section v-for="group in question.groups" :key="group.key"><h4>{{ group.label }}</h4><article v-for="item in group.items" :key="item.key" class="answer-feature"><header><strong>{{ item.label }}</strong><span>{{ scoreText(item.score) }}</span></header><blockquote v-if="item.quote">{{ item.quote }}</blockquote><p>{{ item.comment }}</p><p v-if="item.suggestion"><b>Suggestion:</b> {{ item.suggestion }}</p></article></section><p v-if="!question.groups.length">Detailed feature evidence is not available for this answer.</p></details>
          </div>
        </details>
      </section>
    </template>
  </section>
</template>

<script>
import { api } from './api'
import RadarChart from './RadarChart.vue'
export default {
  name: 'FeedbackReport', components: { RadarChart },
  props: { sessionId: { type: String, required: true } },
  data: () => ({ data: null, loading: false, error: '', active: 'overview', expanded: false, printing: false, loadToken: 0 }),
  watch: { sessionId: { immediate: true, handler() { this.active='overview'; this.data=null; this.load() } } },
  mounted() { this.beforePrint=()=>{this.printing=true}; this.afterPrint=()=>{this.printing=false}; window.addEventListener('beforeprint',this.beforePrint); window.addEventListener('afterprint',this.afterPrint) },
  beforeDestroy() { this.loadToken++; window.removeEventListener('beforeprint',this.beforePrint); window.removeEventListener('afterprint',this.afterPrint) },
  methods: {
    async load() { const token=++this.loadToken; this.loading=true; this.error=''; try { const data=await api(`/api/speaking/sessions/${encodeURIComponent(this.sessionId)}/report-data`); if(token===this.loadToken)this.data=data } catch(error) { if(token===this.loadToken)this.error=error.message } finally { if(token===this.loadToken)this.loading=false } },
    valid(value) { return typeof value==='number' && Number.isFinite(value) && value>=0 && value<=10 },
    scoreText(value) { return this.valid(value)?`${value}/10`:'Not assessed' },
    statusText(value) { return value==='skipped'?'Skipped':value==='available'?'Assessed':value==='unavailable'?'No reliable transcript':'Details available' },
  },
}
</script>

<style scoped src="./feedback-report.css"></style>
