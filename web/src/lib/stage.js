// 거름망 장면과 칩 만들기 장면이 같이 쓰는 무대 좌표. 칩 만들기의 마지막 칩 자리 = 거름망 AI 영역 칩 자리
export const W = 1200;                  // 무대 폭. 화면 폭에 맞춰 줄이고 키운다
export const AI_ROWS = [86, 134], AI_ZONE_H = 170;

export const spread = (n, i, left = 90, right = W - 90) => (n === 1 ? W / 2 : left + (i * (right - left)) / (n - 1));
/** 칩 진하기 3단계: 그 이유가 나온 AI 답 비율 */
export const tier = share => (share >= 0.3 ? 3 : share >= 0.12 ? 2 : 1);
export const chipScale = share => 0.86 + Math.min(share, 0.6) * 0.5;
/** AI 칩 i번(많이 나온 순, 모두 n개)의 처음 자리. 두 줄로 나눠 놓는다 */
export function aiHome(i, n) {
  const perRow = Math.ceil(n / 2);
  const row = i < perRow ? 0 : 1, k = row ? i - perRow : i, m = row ? n - perRow : perRow;
  return { x: spread(m, k, 150, W - 150), y: AI_ROWS[row] };
}
