// 由 `scripts/gen_web_types.py` 生成，请勿手改。
// 覆盖范围：FastAPI 组件 schema（Pydantic 模型）；dict 端点不在其中。

export interface components {
  schemas: {
    HTTPValidationError: {
      detail?: components["schemas"]["ValidationError"][];
    };
    InjectRequest: {
      prompt: string;
    };
    RunRequest: {
      run_id?: string | null;
      max_usd?: number | null;
      focus_hint?: string | null;
      wait?: boolean;
    };
    TopicCreate: {
      id: string;
      name: string;
      description?: string;
      scope_statement: string;
      scope_keywords?: string[];
      seed_queries?: string[];
      sources?: unknown[];
    };
    TopicUpdate: {
      name?: string | null;
      description?: string | null;
      scope_statement?: string | null;
      scope_keywords?: string[] | null;
      seed_queries?: string[] | null;
      status?: string | null;
    };
    ValidationError: {
      loc: string | number[];
      msg: string;
      type: string;
      input?: unknown;
      ctx?: unknown;
    };
  };
}
