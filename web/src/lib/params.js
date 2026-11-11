import { useSearchParams } from "react-router-dom";
import { BASE_MODELS, FEATURES, KINDS, SERVICES } from "./data.js";
import { PLATFORMS } from "./services.js";

export const PARAMS = {
  service: { list: SERVICES, def: "linkareer", label: "서비스" },
  feature: { list: FEATURES, def: "F3", label: "기능" },
  kind: { list: KINDS, def: "nouse", label: "이유" },
  platform: { list: PLATFORMS, def: "app", label: "플랫폼" },
};

/** 페르소나를 씌울 바탕 모델 (팀 결정 대기). 주소 ?base=model_a 에 남긴다 */
export function useBaseModel() {
  const [sp, setSp] = useSearchParams();
  const base = BASE_MODELS.some(m => m.id === sp.get("base")) ? sp.get("base") : BASE_MODELS[0].id;
  const set = id => { const n = new URLSearchParams(sp); n.set("base", id); setSp(n, { replace: true }); };
  return [base, set];
}

/** 서비스·기능·이유 종류를 주소(?service=…)에 담는다. 화면 6에서 칸을 누르면 그대로 화면 5로 넘어온다 */
export function useCellParams() {
  const [sp, setSp] = useSearchParams();
  const get = k => (PARAMS[k].list.some(x => x.id === sp.get(k)) ? sp.get(k) : PARAMS[k].def);
  const set = (k, v) => { const n = new URLSearchParams(sp); n.set(k, v); setSp(n, { replace: true }); };
  return { service: get("service"), feature: get("feature"), kind: get("kind"), platform: get("platform"), set };
}

