<script setup>
defineProps({
  title: { type: String, required: true },
})
</script>

<template>
  <details class="accordion">
    <summary>
      <span>{{ title }}</span>
      <svg aria-hidden="true" viewBox="0 0 20 20" fill="none">
        <path d="m5 8 5 5 5-5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </summary>
    <div class="accordion-content">
      <slot />
    </div>
  </details>
</template>

<style scoped>
.accordion {
  margin-top: 24px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #192430;
}

summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  min-height: 52px;
  padding: 12px 16px;
  border-radius: 11px;
  list-style: none;
  font-weight: 650;
  cursor: pointer;
}

summary::-webkit-details-marker { display: none; }
summary:hover { background: #243343; }

svg {
  flex: none;
  width: 20px;
  height: 20px;
  color: var(--accent);
}

[open] > summary { border-radius: 11px 11px 0 0; }
[open] > summary svg { transform: rotate(180deg); }

.accordion-content {
  border-top: 1px solid var(--line);
  padding: 16px;
}

.accordion-content :slotted(p) {
  max-width: 80ch;
  margin: 0;
}

.accordion-content :slotted(p + p) { margin-top: 12px; }
</style>
