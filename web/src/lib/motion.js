// 장면 부품이 같이 쓰는 움직임 도구
import { useEffect, useLayoutEffect, useState } from "react";

export const reduceMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** 무대(고정 좌표 w)를 상자 폭에 맞춰 줄이고 키우는 비율 */
export function useFit(ref, w) {
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setScale(el.clientWidth / w));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, w]);
  return scale;
}

/**
 * 박자 안의 잔걸음. key(보통 박자 번호)가 바뀌면 0부터 다시 세고, offsets[i] ms가 지나면 i가 된다.
 * 움직임 줄이기 설정이면 바로 마지막 걸음
 */
export function useSub(key, offsets) {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (reduceMotion()) { setI(offsets.length - 1); return; }
    setI(0);
    const ts = offsets.slice(1).map((t, k) => setTimeout(() => setI(k + 1), t));
    return () => ts.forEach(clearTimeout);
    // offsets는 key마다 정해져 있다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return i;
}

/** run이 true가 되면 0 → 1로 dur ms 동안 오르는 값 (숫자 올라가는 효과) */
export function useRamp(run, dur = 1400) {
  const [v, setV] = useState(run ? 1 : 0);
  useEffect(() => {
    if (!run) { setV(0); return; }
    if (reduceMotion()) { setV(1); return; }
    let raf, t0;
    const step = t => {
      t0 ??= t;
      const k = Math.min(1, (t - t0) / dur);
      setV(1 - (1 - k) ** 3);
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [run, dur]);
  return v;
}
