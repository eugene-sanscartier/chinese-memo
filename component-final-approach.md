# Work Stream: component final approach

## Files in scope

- `data_components.py`
- `data/derived/components/components.json`
- `data/derived/components/approaches/`
- `data/source/authored/component_entity_standard_map.json`
- `tools/components/generate_component_approaches.py`
- `AGENTS.md`

## Goal

Create a final component approach file for later Anki-card use, based on the direct approach.

## Confirmed decisions

- Deliverable is a data artifact only for now.
- Base the final approach on the direct approach only.
- Write a new final JSON instead of overwriting an existing approach file.
- Match the existing component-output JSON shape, using the previous final file shape as the format example.
- Refine the direct approach with learner-facing normalization, but keep direct depth-1 chunks by default instead of recursively unwrapping them.
- Include the shared family component context in the final output by using `family + final`, deduplicated.
- Respect structural component order in the final output instead of forcing all family components to the front.
- Use learner-facing named forms in `final` only when raw IDS pieces are opaque or variant-only.
- Normalize learner-facing forms in `final`, including `⺌ -> 小`, `⺮ -> 竹`, `𧾷 -> 足`, `𤣩 -> 王`, `礻 -> 示`, and `⻏/⻖ -> 阝`.
- Keep direct depth-1 chunks by default; do not preserve or unwrap chunks based on study-set membership.
- Prefer `尚` over variant top forms such as `𫩠` and `龸`.

## Evaluation criteria

- The new final file keeps the same top-level `{char: [comp, ...]}` shape as the current component outputs.
- The derivation from the direct approach is explicit in `data_components.py`.
- Existing approach files are preserved.
- The final approach is more card-usable than raw direct output for opaque single-chunk cases.
- The final approach should keep intuitive slot order for mixed `family` + refined-direct outputs such as `吵=['口','少']` and `吊=['口','巾']`.
- `final` should remove raw `𫩠`, `龸`, and `&CDP-8958;` in favor of learner-facing components.
- `final` should normalize visible top `⺌` to learner-facing `小`.
- A separate authored map can propose replacements for raw IDS entity components without mutating `final` yet.
- `final` should avoid recursive unwrapping that creates mixed granularity or partial-loss stumps such as `验 -> 亼`.

## Progress

- Inspected the current direct, all, hanzi, rare, and contrastive outputs.
- Confirmed that `data_components_direct.json` is already the correct target format precedent.
- Confirmed the remaining design fork: whether to keep direct exactly or unwrap opaque direct chunks.
- Confirmed the final approach should be direct-based with one-level unwrapping.
- Implemented the final component generator in `data_components.py`.
- Regenerated the component outputs and confirmed the final approach keeps the same non-empty coverage as `direct` while changing 389 characters.
- Verified representative improvements: `尚` → `['冂', '口']`, `尝` → `['小', '冖']`, `耀` → `['羽', '隹']`.
- Updated final ordering so shared family components follow structural appearance instead of always coming first.
- Identified the current-study characters directly affected by hidden top-form filtering:
  - `⺌`: `当`, `尚`, `肖`
  - nested `⺌` top chunk: `光`
  - `龸`: `尝`
  - `𫩠`: `常`, `党`, `掌`, `堂`, `赏`, `棠`, `裳`
- Updated `final` generation only so it:
  - normalizes `𫩠 -> 尚`
  - normalizes `龸 -> 尚`
  - normalizes `&CDP-8958; -> 月`
  - preserves visible `⺌` in learner-facing `final`
  - expands one nested top-level IDS child for cases like `光`
- Regenerated `final` and verified key outputs now read:
  - `当 -> ['⺌', '彐']`
  - `光 -> ['⺌', '儿']`
  - `尚 -> ['⺌', '冂', '口']`
  - `常/党/掌/堂/赏/棠/裳 -> ['尚', ...]`
  - `尝 -> ['尚', '云']`
  - `肖 -> ['⺌', '月']`
- Added `data/source/authored/component_entity_standard_map.json` as a reviewable replacement map for entity components still present in the final output.
- The map is inferred from host-character context, not only from the raw entity code:
  - for each entity, compare the host character's `final` components against memodevice components and MMA phonetic/semantic fields
  - aggregate the missing candidates across the characters where the entity appears
  - keep only confident winners in `mapped`; leave the rest in `unresolved_entities`
- Current authored map coverage:
  - `35` contextual replacements
  - `65` unresolved entity components left for later review
- `final` itself was intentionally not modified in that step.
- Refactored the pipeline layout so:
  - `data_components.py` is final-only and writes `data/derived/components/components.json`
  - legacy non-final approach generation lives in `tools/components/generate_component_approaches.py`
  - non-final approach outputs live in `data/derived/components/approaches/`
- Re-audited the final output for decomposition quality, including over-unwrapping, mixed granularity, partial-loss, and learner-facing normalization issues.
- Identified the main algorithmic bug: direct chunks were being recursively unwrapped based on study-set membership, which produced regressions like `数=['米','女','攵']`, `痛=['疒','龴','用']`, `幅=['巾','𠮛','田']`, and entity-heavy fallouts like `瞬=['目','&CDP-8BB8;','舛']`.
- Replaced that behavior so `final` now keeps normalized depth-1 direct chunks by default and builds `family` on the same normalized direct view.
- Regenerated `final` and verified the former over-unwrapped families now read:
  - `数/屡/缕/楼/搂 -> 娄`
  - `痛/通/诵/勇/桶/涌 -> 甬`
  - `辐/幅/副/富/逼/福 -> 畐`
  - `褐/遏/歇/葛/喝/渴 -> 曷`
  - `躁/燥/噪/澡 -> 喿`
  - `蹈/稻/滔 -> 舀`
  - `验/签/险/剑/敛/脸/检 -> 佥`
- Verified learner-facing normalization now reads:
  - `肖 -> ['小','月']`
  - `当 -> ['小','彐']`
  - `光 -> ['小','儿']`
  - `路 -> ['足','各']`
  - `神 -> ['示','申']`
  - `珠 -> ['王','朱']`
  - `部 -> ['咅','阝']`
- Verified the harmful algorithmic mixed-granularity cases are gone and partial-loss unwrapping is eliminated:
  - old bad cases like `骸/孩/核/咳`, `抗`, `操`, `揭`, `俭`, `浇` no longer contain both a re-added parent and the split children created by recursive unwrapping
  - `0` partial-loss cases remain in the regenerated final output
