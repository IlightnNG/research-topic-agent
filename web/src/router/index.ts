import { createRouter, createWebHistory } from 'vue-router'
import TopicsView from '@/views/TopicsView.vue'
import TopicReportView from '@/views/TopicReportView.vue'
import TopicChatView from '@/views/TopicChatView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'topics', component: TopicsView },
    { path: '/topics/:topicId/report', name: 'topic-report', component: TopicReportView },
    { path: '/topics/:topicId/chat', name: 'topic-chat', component: TopicChatView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
