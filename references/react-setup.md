# React + Babel 项目规范

用HTML+React+Babel做原型时必须遵守的技术规范。不遵守会炸。

## Pinned Script Tags（必须用这些版本）

在HTML的`<head>`里放这三个script tag，用**固定版本+integrity hash**：

```html
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js" integrity="sha384-hD6/rw4ppMLGNu3tX5cjIb+uRZ7UkRJ6BPkLpg4hAu/6onKUg4lLsHAs9EBPT82L" crossorigin="anonymous"></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" integrity="sha384-u6aeetuaXnQ38mYT8rp6sbXaQe3NL9t+IBXmnYxwkUI2Hw4bsp2Wvmx4yRQF1uAm" crossorigin="anonymous"></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" integrity="sha384-m08KidiNqLdpJqLq95G/LEi8Qvjl/xUYll3QILypMoQ65QorJ9Lvtp2RXYGBFj1y" crossorigin="anonymous"></script>
```

**不要**用`react@18`或`react@latest`这种unpinned版本——会出现版本漂移/缓存问题。

**不要**省略`integrity`——CDN一旦被劫持或篡改，这是防线。

## 文件结构

**默认单页 inline**：屏、样式、数据与图片同页，`file://` 双击可开（见 `app-prototype.md` §0）。只有超过 ~1000 行难维护、或需要多 agent 并行时才拆分，拆分后必须在交付说明里给启动命令（不能双击直接打开的拆分等同于降级）。

拆分时用相对路径 + 本地 `vendor/` 或 `type="text/babel" src="components.jsx"` 均可，但必须实测 `file://` 下能加载；**不要**用`type="module"`——会和Babel冲突。

## 三条不可违反的规矩

### 规矩1：styles 对象必须用唯一命名

**错误**（多组件时必炸）：
```jsx
// components.jsx
const styles = { button: {...}, card: {...} };

// pages.jsx  ← 同名覆盖！
const styles = { container: {...}, header: {...} };
```

**正确**：每个组件文件的styles用唯一前缀。

```jsx
// terminal.jsx
const terminalStyles = { 
  screen: {...}, 
  line: {...} 
};

// sidebar.jsx
const sidebarStyles = { 
  container: {...}, 
  item: {...} 
};
```

**或者用inline styles**（小组件推荐）：
```jsx
<div style={{ padding: 16, background: '#111' }}>...</div>
```

这条是**非协商**的。每次写`const styles = {...}`都必须replace成specific命名，否则多组件加载时全栈报错。

### 规矩2：Scope 不共享，需手动export

**关键认知**：每个`<script type="text/babel">`被Babel独立编译，它们之间**scope不通**。`components.jsx`里定义的`Terminal`组件，在`pages.jsx`里**默认是undefined**。

**解决方式**：在每个组件文件末尾，把要共享的组件/工具export到`window`：

```jsx
// components.jsx 末尾
function Terminal(props) { ... }
function Line(props) { ... }
const colors = { green: '#...', red: '#...' };

Object.assign(window, {
  Terminal, Line, colors,
  // 所有你要在别处用的都列在这里
});
```

然后`pages.jsx`就能直接用`<Terminal />`，因为JSX会去`window.Terminal`找。

### 规矩3：不要用 scrollIntoView

`scrollIntoView`会把整个HTML容器往上推，搞坏web harness的布局。**永远不要用**。

替代方案：
```js
// 滚到容器内某个位置
container.scrollTop = targetElement.offsetTop;

// 或者用element.scrollTo
container.scrollTo({
  top: targetElement.offsetTop - 100,
  behavior: 'smooth'
});
```

## 原型里的 mock 数据

HTML 原型**不在运行时调用外部 LLM API**：既不需要 key，也避免 CORS 与凭据泄漏。需要对话/生成类演示时，在当前 agent 会话里先生成 mock 响应数据，再硬编码进 HTML，返回预设文案并保留合理延迟即可。

## 典型 HTML 起手模板

拷贝这个模板作为React原型的骨架：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Your Prototype Name</title>

  <!-- React + Babel pinned -->
  <script src="https://unpkg.com/react@18.3.1/umd/react.development.js" integrity="sha384-hD6/rw4ppMLGNu3tX5cjIb+uRZ7UkRJ6BPkLpg4hAu/6onKUg4lLsHAs9EBPT82L" crossorigin="anonymous"></script>
  <script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" integrity="sha384-u6aeetuaXnQ38mYT8rp6sbXaQe3NL9t+IBXmnYxwkUI2Hw4bsp2Wvmx4yRQF1uAm" crossorigin="anonymous"></script>
  <script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" integrity="sha384-m08KidiNqLdpJqLq95G/LEi8Qvjl/xUYll3QILypMoQ65QorJ9Lvtp2RXYGBFj1y" crossorigin="anonymous"></script>

  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; width: 100%; }
    body { 
      font-family: -apple-system, 'SF Pro Text', sans-serif;
      background: #FAFAFA;
      color: #1A1A1A;
    }
    #root { min-height: 100vh; }
  </style>
</head>
<body>
  <div id="root"></div>

  <!-- 你的组件文件 -->
  <script type="text/babel" src="components.jsx"></script>

  <!-- 主入口 -->
  <script type="text/babel">
    const { useState, useEffect } = React;

    function App() {
      return (
        <div style={{padding: 40}}>
          <h1>Hello</h1>
        </div>
      );
    }

    const root = ReactDOM.createRoot(document.getElementById('root'));
    root.render(<App />);
  </script>
</body>
</html>
```

## 常见报错及解决

**`styles is not defined` 或 `Cannot read property 'button' of undefined`**
→ 你在一个文件里定义了`const styles`，另一个文件覆盖了。给每个改成specific命名。

**`Terminal is not defined`**
→ 跨文件引用时scope不通。在定义Terminal的文件末尾加`Object.assign(window, {Terminal})`。

**整个页面白屏，控制台没错误**
→ 多半是JSX语法错误但Babel没报在控制台。把`babel.min.js`临时换成`babel.js`非压缩版，错误信息更清晰。

**ReactDOM.createRoot is not a function**
→ 版本不对。确认用了react-dom@18.3.1（而不是17或其他）。

**`Objects are not valid as a React child`**
→ 你渲染了一个对象而不是JSX/字符串。通常是`{someObj}`写成了`{someObj.name}`。

## 大项目怎么拆文件

**>1000行的单文件**难维护。分拆思路：

```
项目/
├── index.html
├── src/
│   ├── primitives.jsx      # 基础元素：Button、Card、Badge...
│   ├── components.jsx      # 业务组件：UserCard、PostList...
│   ├── pages/
│   │   ├── home.jsx        # 首页
│   │   ├── detail.jsx      # 详情页
│   │   └── settings.jsx    # 设置页
│   ├── router.jsx          # 简单路由（React state切换）
│   └── app.jsx             # 入口组件
└── data.js                 # mock data
```

HTML里按顺序加载：
```html
<script type="text/babel" src="src/primitives.jsx"></script>
<script type="text/babel" src="src/components.jsx"></script>
<script type="text/babel" src="src/pages/home.jsx"></script>
<script type="text/babel" src="src/pages/detail.jsx"></script>
<script type="text/babel" src="src/pages/settings.jsx"></script>
<script type="text/babel" src="src/router.jsx"></script>
<script type="text/babel" src="src/app.jsx"></script>
```

**每个文件末尾**都要`Object.assign(window, {...})`导出要共享的东西。


---

## 附录：技术红线

> 入口见 `SKILL.md`；本文件是展开。

**React+Babel 项目**必须用 pinned 版本（见上文）。三条不可违反：

1. **never** 写 `const styles = {...}`——多组件时命名冲突会炸。**必须**给唯一名字：`const terminalStyles = {...}`
2. **scope 不共享**：多个 `<script type="text/babel">` 之间组件不通，必须用 `Object.assign(window, {...})` 导出
3. **never** 用 `scrollIntoView`——会搞坏容器滚动，用其他 DOM scroll 方法
4. **手写动效**必须实现两件事：(a) 首帧同步设 `window.__ready = true`，截图/验证才拿得到稳定画面 (b) 尊重 `prefers-reduced-motion`，减少动效时布局不塌

**设备框**：App 原型必须用 `assets/ios_frame.jsx` / `assets/android_frame.jsx`，禁止手写状态栏、Dynamic Island、home indicator 与 bezel。

**固定尺寸容器**（如 1:1 设计基准的设备屏）需要缩放时用 auto-scale + letterboxing，不用滚动条凑。
