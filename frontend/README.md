# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```


# Project structure
src/
├── domain/               # Lớp trung tâm: Chứa Entities và Interfaces
│   ├── models/           # Các TypeScript Interfaces lấy từ openapi.json (VD: User, ChatMessage)
│   └── repositories/     # Interfaces định nghĩa các hàm gọi API (Không chứa logic implement)
│
├── infrastructure/       # Lớp hạ tầng: Giao tiếp với thế giới bên ngoài (API, LocalStorage)
│   ├── api/              # Cấu hình Axios instance, Interceptors (gắn token)
│   ├── services/         # Implement các repositories từ lớp Domain
│   └── local_storage/    # Xử lý lưu/đọc Token
│
├── application/          # Lớp ứng dụng: Chứa Use Cases và State Management
│   ├── hooks/            # Custom hooks kết nối UI với Services (VD: useChat, useAuth)
│   └── store/            # Global state (Zustand/Redux)
│
└── presentation/         # Lớp hiển thị: UI Components (Nơi reachat.dev tỏa sáng)
    ├── components/       # Các UI component dùng chung (Button, Layout)
    ├── features/         # Gom nhóm UI theo tính năng (chat, auth, sidebar)
    └── pages/            # Các trang chính (ChatPage, LoginPage)