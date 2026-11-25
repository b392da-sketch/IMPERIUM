# EF09-RH1 integrated displacement regressions

Original orientation unless indicated. Red exits at r=8 and Blue at r=0.
Custom fixtures contain only the listed units. Facing defaults are Red f4
and Blue f1. R denotes routing, O organized. The same batch entry point
is used by accepted assault roots and round closure.

| Case | Frozen inputs and trigger | Expected result |
| --- | --- | --- |
| Edge exit | Red R0 (4,8), Red R1 (4,7), Red O2 (3,8), trigger 0/1 | 0 exits, 1 blocked; no follow into (4,8) |
| Contested | Red R0 (4,7), Red R1 (5,7), Red O2 (3,8), Red O3 (5,8), trigger 0/1 | Both contest (4,8); no movement |
| Fallback | Red R0 (4,3), Blue R6 (4,5), trigger 0/6 | Contest (4,4); reserve (3,4) and (5,4) |
| Repulse then rout | Red O0 (4,6), C1 M1, Red O1 (4,7), Red O2 (3,7); melee C+1 then M+1 | Repulse blocked, then C2 M2 routes without movement, even if blocker leaves |
| Exit allowance | Red R0 (4,7), Red O1 (3,8), two consecutive triggers | First reaches (4,8); second cannot exit |
| Frozen threat | Red R0 (4,3), Blue O6 (4,5) f4, trigger rout 0 and displacement 6 | Blue leaves its original cell; Red still cannot enter original threat (4,4) and goes to (3,4) |
| Stationary primary | Red R0 (4,7), Red O1 (4,8) | Router chooses (3,8) |
| Mirror | Rotate fallback inputs and reverse trigger order | The same logical assignments after rotating back |

The frozen-threat setup deliberately invokes the displacement stage with
an organized opposing threat source. It tests the snapshot contract directly,
independently of which condition effect selected the mover.
