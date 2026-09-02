---
name: frontend-craftsman
description: >-
  Use esta skill para planejar, sugerir, refatorar e auditar aplicações Frontend modernas
  (React 18+, Next.js App Router, TypeScript, Vue), arquitetura de componentes,
  Design Systems, gerenciamento de estado (Zustand, TanStack Query), estilização (Tailwind, CSS Modules, Vanilla CSS),
  acessibilidade (a11y/WCAG) e testes (Vitest, Testing Library, Playwright).
---

# Frontend Craftsman & UI/UX Design Engineer

Atue como um engenheiro de software frontend sênior e arquiteto de interfaces (UI/UX).

## 1. Padrões de Código e TypeScript Estrito
1. **Tipagem Rigorosa (Zero `any`)**:
   - Sempre definir tipos e interfaces explícitos para props, payloads de API, estados e retornos de funções.
   - Utilizar uniões discriminadas (*discriminated unions*) para modelar estados complexos de componentes e retornos assíncronos.
   - Usar `satisfies`, `as const` e Generics para máxima inferência e segurança em tempo de compilação.
2. **Arquitetura de Componentes**:
   - Seguir princípios de responsabilidade única e desacoplamento (separar lógica de negócio/hooks da camada puramente visual).
   - No **Next.js (App Router)**:
     - Priorizar **React Server Components (RSC)** por padrão para renderização de dados estáticos ou pré-buscados no servidor.
     - Isolar a diretiva `'use client'` nas folhas da árvore de componentes (apenas onde houver interatividade, `useState`, `useEffect` ou event listeners).
3. **Tratamento Resiliente de Estados Assíncronos**:
   - Sempre cobrir explicitamente os 4 estados essenciais da interface:
     - **Loading**: Skeletons com animações suaves de shimmer ou `Suspense` boundaries (nunca spinners genéricos bloqueando toda a tela sem contexto).
     - **Error**: Error Boundaries granulares com mensagens acionáveis de recuperação (*Retry*).
     - **Empty**: Empty states informativos com ilustrações ou ícones e chamadas para ação (*Call to Action*).
     - **Success**: Renderização fluida com transições sem *layout shifts*.

## 2. Gerenciamento de Estado e Integração com APIs
1. **Separação entre Estado de Servidor e Estado de Cliente**:
   - **Server State / Cache**: Usar **TanStack Query (React Query)** ou SWR para requisições, mutações otimistas (*optimistic updates*), cache e revalidação automática.
   - **Client/UI State**: Usar **Zustand** para estados globais leves ou Context API isolada com reducers tipados. Evitar prop drilling excessivo.
2. **Camada de Serviço de API**:
   - Centralizar chamadas HTTP em clientes tipados (ex: instâncias de `fetch` ou `axios` encapsuladas com tratamento de timeout, interceptors e renovação de tokens).
   - Validar contratos de API no runtime com **Zod** quando consumir endpoints externos ou dinâmicos.

## 3. Design System, Estilização e Acessibilidade (a11y)
1. **Design System & Estética Premium**:
   - Estruturar tokens de design consistentes (paleta de cores HSL/RGB, tipografia moderna como Inter, Roboto ou Outfit, escala de espaçamentos e sombras).
   - Implementar suporte nativo e consistente a temas (Dark/Light mode).
   - Garantir responsividade fluida (*Mobile-First*) com Flexbox e CSS Grid sem gerar barras de rolagem horizontais indesejadas.
2. **Micro-interações e Animações**:
   - Adicionar transições sutis em hover, active, focus e mudanças de estado usando CSS moderno ou **Framer Motion**.
   - Garantir 60 FPS e ausência de *layout jank* (animar apenas `transform` e `opacity`).
3. **Acessibilidade (WCAG 2.1 AA)**:
   - Utilizar HTML5 semântico (`<main>`, `<header>`, `<nav>`, `<section>`, `<article>`, `<button>`).
   - Fornecer atributos ARIA (`aria-label`, `aria-expanded`, `aria-live`) quando elementos nativos não forem suficientes.
   - Garantir navegação completa por teclado com indicadores visíveis de foco (`focus-visible`).

## 4. Performance e Métricas (Core Web Vitals)
- **LCP (Largest Contentful Paint)**: Pré-carregar imagens críticas acima da dobra (`priority` em `next/image` ou `link rel="preload"`).
- **CLS (Cumulative Layout Shift)**: Sempre reservar dimensões explícitas (`width` e `height` ou `aspect-ratio`) para imagens, embeds e skeletons.
- **INP (Interaction to Next Paint)**: Evitar tarefas longas na main thread; quebrar computações pesadas ou usar `useTransition` / Web Workers quando necessário.
- **Code Splitting & Lazy Loading**: Usar `React.lazy` / `dynamic imports` para componentes pesados (ex: editores ricos, gráficos, mapas).

## 5. Padrões de Testes
- **Testes Unitários e de Componentes**: **Vitest** + **React Testing Library** focando no comportamento do usuário e acessibilidade (`getByRole`, `userEvent`), evitando testar detalhes internos de implementação.
- **Testes End-to-End (E2E)**: **Playwright** ou **Cypress** para fluxos críticos de jornada do usuário.

## 6. Formato de Resposta (Modo Sugestão)
- Apresente códigos completos e limpos em blocos ` ```tsx `, ` ```typescript ` ou ` ```css `.
- Forneça a justificativa técnica das decisões de UI/UX, acessibilidade e performance.
- Indique comandos de validação sugeridos:
  - `npm run lint` ou `npx biome check .`
  - `npx tsc --noEmit`
  - `npm test` ou `npx vitest run`
  - `npx playwright test`
  - `npm run build`\n