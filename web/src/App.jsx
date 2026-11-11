import { NavLink, Outlet, Route, Routes } from "react-router-dom";
import Home from "./pages/Home.jsx";
import Service from "./pages/Service.jsx";
import Mvp from "./pages/Mvp.jsx";
import Ask from "./pages/Ask.jsx";
import Extract from "./pages/Extract.jsx";
import Coding from "./pages/Coding.jsx";
import Reasons from "./pages/Reasons.jsx";
import TrustMap from "./pages/TrustMap.jsx";

import { STEPS } from "./lib/steps.js";

const PAGES = { service: <Service />, mvp: <Mvp />, ask: <Ask />, extract: <Extract />, coding: <Coding />, reasons: <Reasons />, map: <TrustMap /> };

function Layout() {
  return (
    <>
      <header className="gnb">
        <div className="in">
          <NavLink to="/" className="logo"><i />SimTrust</NavLink>
          <nav aria-label="단계">
            {STEPS.map(s => (
              <NavLink key={s.path} to={s.path} className={({ isActive }) => (isActive ? "on" : "")}>
                <b>{s.no}</b>{s.name}{s.preview ? <small>미리보기</small> : !s.ready && <small>틀</small>}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="in"><Outlet /></main>
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        {STEPS.map(s => <Route key={s.path} path={s.path} element={PAGES[s.path]} />)}
      </Route>
    </Routes>
  );
}
