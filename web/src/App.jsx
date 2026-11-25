import { Navigate, NavLink, Outlet, Route, Routes } from "react-router-dom";
import Home from "./pages/Home.jsx";
import Demo from "./pages/Demo.jsx";
import TrustMap from "./pages/TrustMap.jsx";
import Quick from "./pages/Quick.jsx";
import { NAV } from "./lib/steps.js";

function Layout() {
  return (
    <>
      <header className="gnb">
        <div className="in">
          <NavLink to="/" className="logo"><i />SimTrust</NavLink>
          <nav aria-label="메뉴">
            {NAV.map(s => <NavLink key={s.path} to={s.path} className={({ isActive }) => (isActive ? "on" : "")}>{s.name}</NavLink>)}
          </nav>
          {/* 가짜 견본·지어낸 예시라는 표시는 화면마다 달지 않고 여기 한 번만 */}
          <span className="demo-pill" title="실제 실험 결과가 나오면 같은 화면에 그대로 바꿔 넣어요">예시 데이터</span>
        </div>
      </header>
      <main className="in"><Outlet /></main>
    </>
  );
}

export default function App() {
  return (
    <Routes>
      {/* 발표용 한눈에 보기: 위쪽 메뉴 없이 화면을 꽉 채운다 */}
      <Route path="quick" element={<Quick />} />
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="demo" element={<Demo />} />
        <Route path="map" element={<TrustMap />} />
        {/* 11/21 전 주소: 화면 1~5는 시연 한 페이지로 합쳤고, 새 MVP 점검은 뺐다 */}
        {["service", "ask", "extract", "coding"].map(p => <Route key={p} path={p} element={<Navigate to="/demo" replace />} />)}
        <Route path="reasons" element={<Navigate to="/demo?go=sieve" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
