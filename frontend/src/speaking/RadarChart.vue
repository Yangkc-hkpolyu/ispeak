<!-- Adapted from PolyInterview's native SVG RadarChart; raw practice scores and missing evidence are retained. -->
<template>
  <figure class="assessment-radar">
    <svg v-if="items.length >= 3" :viewBox="`0 0 ${size} ${size}`" role="img" :aria-label="description">
      <title>{{ title }}</title><desc>{{ description }}</desc>
      <polygon v-for="level in 5" :key="'grid'+level" :points="gridPoints(level)" fill="none" stroke="#d8e3da" />
      <line v-for="(point,index) in outerPoints" :key="'axis'+index" :x1="cx" :y1="cy" :x2="point.x" :y2="point.y" stroke="#d8e3da" />
      <polygon v-if="complete" :points="valuePolygonPoints" fill="#dcebe2" stroke="#2f6558" stroke-width="2.5" stroke-linejoin="round" />
      <g v-for="(item,index) in items" :key="item.key">
        <text :x="labelPos(index).x" :y="labelPos(index).y" text-anchor="middle" class="radar-name">{{ shortLabel(item) }}</text>
        <text :x="labelPos(index).x" :y="labelPos(index).y+19" text-anchor="middle" class="radar-score">{{ scoreText(item.score) }}</text>
        <circle v-if="valid(item.score)" :cx="pointAt(index,item.score/10).x" :cy="pointAt(index,item.score/10).y" r="5" fill="#2f6558" stroke="white" stroke-width="2"><title>{{ item.label }}: {{ scoreText(item.score) }}. {{ item.comment }}</title></circle>
      </g>
      <text :x="cx+7" :y="cy-radius+12" class="radar-scale">10</text>
    </svg>
    <figcaption>{{ complete ? 'Four text-based practice dimensions, scored out of 10.' : 'Unassessed dimensions are not plotted as zero. A complete shape requires four scores.' }}</figcaption>
  </figure>
</template>

<script>
export default {
  name: 'RadarChart',
  props: { items: { type: Array, required: true }, title: { type: String, default: 'Speaking practice assessment' }, size: { type: Number, default: 400 } },
  computed: {
    cx() { return this.size / 2 }, cy() { return this.size / 2 }, radius() { return this.size * .27 },
    complete() { return this.items.length >= 3 && this.items.every(item => this.valid(item.score)) },
    outerPoints() { return this.items.map((_,index) => this.pointAt(index,1)) },
    valuePolygonPoints() { return this.items.map((item,index) => { const p = this.pointAt(index,item.score/10); return `${p.x},${p.y}` }).join(' ') },
    description() { return this.items.map(item => `${item.label}: ${this.scoreText(item.score)}`).join('. ') },
  },
  methods: {
    valid(value) { return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 10 },
    scoreText(value) { return this.valid(value) ? `${value}/10` : 'Not assessed' },
    angleAt(index) { return -Math.PI / 2 + index * (2 * Math.PI / this.items.length) },
    pointAt(index,fraction) { const angle = this.angleAt(index); return { x: this.cx + fraction * this.radius * Math.cos(angle), y: this.cy + fraction * this.radius * Math.sin(angle) } },
    gridPoints(level) { return this.items.map((_,index) => { const p = this.pointAt(index,level/5); return `${p.x},${p.y}` }).join(' ') },
    labelPos(index) { return this.pointAt(index,1.3) },
    shortLabel(item) { return ({coherence:'Coherence',vocabulary:'Vocabulary',grammar:'Grammar',task_response:'Task response'})[item.key] || item.label },
  },
}
</script>

<style scoped>
.assessment-radar{margin:0;min-width:0}.assessment-radar svg{display:block;width:100%;max-width:400px;margin:auto;overflow:visible}.radar-name{fill:#344b40;font-size:13px;font-weight:600}.radar-score{fill:#53665c;font-size:12px}.radar-scale{fill:#6a7c70;font-size:10px}.assessment-radar figcaption{font-size:12px;line-height:1.6;color:#596c61;text-align:center;max-width:350px;margin:0 auto 12px}
</style>
