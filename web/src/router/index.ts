import { createRouter, createWebHistory } from "vue-router";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/topics" },
    { path: "/topics", name: "topics", component: () => import("@/views/TopicsView.vue") },
    {
      path: "/topics/:topicId",
      name: "topic-reports",
      component: () => import("@/views/TopicReportsView.vue"),
    },
    {
      path: "/topics/:topicId/runs/:runId",
      name: "run",
      component: () => import("@/views/TopicReportsView.vue"),
      props: true,
    },
    {
      path: "/topics/:topicId/chat",
      name: "topic-chat",
      component: () => import("@/views/TopicChatView.vue"),
    },
    {
      path: "/topics/:topicId/chat/:sessionId",
      name: "topic-chat-session",
      component: () => import("@/views/TopicChatView.vue"),
      props: true,
    },
    { path: "/:pathMatch(.*)*", redirect: "/topics" },
  ],
});
