# Final production model inventory

45 artifacts: 44 fitted and one deterministic heuristic. Temporary test fits are excluded. Repeated artifacts/seeds are not independent strategies. Validation and final-test values below are persisted metrics, not newly opened evaluations. Full configurations, curves, checkpoints, source hashes and limitations are in [machine-readable inventory](PROMETHEUS_FINAL_RESEARCH_INVENTORY.json).

| Model | Family | Dataset | Seed | Capacity / budget | Training seconds | Validation | Final test |
|---|---|---|---:|---|---:|---|---|
| `model-006eed74ab6b411ab633c60d` | mlp | `dataset-38ec6e9776097d8e36693372` | 29 | width 32; epoch cap 80 | 9.349 | brier=0.0292882 | Not opened / policy evaluation separate |
| `model-02753b861c1a4b17a72a0e08` | logistic | `dataset-d8c1593a2d281e1c9e430952` | 11 | Linear classifier | 0.071 | brier=0.207456 | Not opened / policy evaluation separate |
| `model-0994f52d25424bfeb5c91a81` | mlp | `dataset-d8c1593a2d281e1c9e430952` | 11 | width 32; epoch cap 80 | 10.306 | brier=0.034718 | Not opened / policy evaluation separate |
| `model-0c4181f1d7b341d1a90434e3` | mlp | `dataset-d8c1593a2d281e1c9e430952` | 11 | width 32; epoch cap 80 | 14.284 | brier=0.204813 | Not opened / policy evaluation separate |
| `model-131794f0434945a286163323` | mlp | `dataset-f53981b7dd24c1521ce749b1` | 11 | width 32; epoch cap 80 | 15.009 | brier=0.0892499 | Not opened / policy evaluation separate |
| `model-249cad7203b24a7cabc6b16a` | cost_mlp | `dataset-2b612fa4cfab325eebc061f3` | 11 | width 32; epoch cap 80 | 15.521 | rmse=0.0951352, mae=0.0634046 | Not opened / policy evaluation separate |
| `model-265cbcc71f6847828c959882` | severity_mlp | `dataset-f53981b7dd24c1521ce749b1` | 29 | width 32; epoch cap 80 | 7.518 | rmse=3.66051, mae=1.67579 | Not opened / policy evaluation separate |
| `model-27006372c7ea4b7d850c0b9c` | ppo | `dataset-38ec6e9776097d8e36693372` | 7 | width 32; transition cap 4096 | 61.637 | See artifact / policy evaluation | Not opened / policy evaluation separate |
| `model-2a56b683c79745bdbec64892` | logistic | `dataset-f53981b7dd24c1521ce749b1` | 29 | Linear classifier | 0.072 | brier=0.0913249 | Not opened / policy evaluation separate |
| `model-2d7322c242794ab1b974dce8` | logistic | `dataset-d8c1593a2d281e1c9e430952` | 11 | Linear classifier | 0.072 | brier=0.0364086 | Not opened / policy evaluation separate |
| `model-3141334b301947499b59913d` | logistic | `dataset-38ec6e9776097d8e36693372` | 7 | Linear classifier | 0.048 | brier=0.0315398 | Recorded |
| `model-32b385e23cf84c68a48ccc68` | logistic | `dataset-d8c1593a2d281e1c9e430952` | 29 | Linear classifier | 0.065 | brier=0.0776202 | Not opened / policy evaluation separate |
| `model-33cddb0d92024c2bb0a3b34a` | ppo | `dataset-38ec6e9776097d8e36693372` | 7 | width 32; transition cap 4096 | 113.900 | See artifact / policy evaluation | Not opened / policy evaluation separate |
| `model-38a8da8c0d7a481d8d2d9771` | ridge | `dataset-f53981b7dd24c1521ce749b1` | 11 | Linear regression | 0.122 | rmse=3.72769, mae=1.80005 | Recorded |
| `model-3a9c422c0e0d420ba8fd568a` | mlp | `dataset-c6247f1456257066f0fe8d5f` | 29 | width 32; epoch cap 80 | 5.995 | brier=0.142153 | Not opened / policy evaluation separate |
| `model-3b9a496d6fad468ba791c1b4` | heuristic | `dataset-38ec6e9776097d8e36693372` | 7 | Deterministic rule | 0.048 | brier=0.0988889 | Recorded |
| `model-3c55d1d8ecae474cb574a8e2` | mlp | `dataset-d8c1593a2d281e1c9e430952` | 29 | width 32; epoch cap 80 | 14.273 | brier=0.0344976 | Not opened / policy evaluation separate |
| `model-4058f9dcf60a4dd39ef3b8ac` | logistic | `dataset-d8c1593a2d281e1c9e430952` | 29 | Linear classifier | 0.065 | brier=0.0364086 | Not opened / policy evaluation separate |
| `model-4198e06e1e3647a587bd0ef3` | mlp | `dataset-c6247f1456257066f0fe8d5f` | 11 | width 32; epoch cap 80 | 6.013 | brier=0.144156 | Not opened / policy evaluation separate |
| `model-47e69b3d348745549167af9a` | logistic | `dataset-c6247f1456257066f0fe8d5f` | 29 | Linear classifier | 0.067 | brier=0.1434 | Not opened / policy evaluation separate |
| `model-5a0f86eceb8c4c689e85d285` | severity_mlp | `dataset-f53981b7dd24c1521ce749b1` | 11 | width 32; epoch cap 80 | 8.051 | rmse=3.66792, mae=1.6811 | Not opened / policy evaluation separate |
| `model-5dbaecfa00a646dead13eebd` | logistic | `dataset-38ec6e9776097d8e36693372` | 29 | Linear classifier | 0.065 | brier=0.0315398 | Not opened / policy evaluation separate |
| `model-5eb01f1d328a4d29bc0166fc` | cost_mlp | `dataset-b5c3dbdac9284f292a949b65` | 11 | width 32; epoch cap 80 | 16.125 | rmse=0.114703, mae=0.0766886 | Not opened / policy evaluation separate |
| `model-83071a76ab8f435787bdaf90` | mlp | `dataset-d8c1593a2d281e1c9e430952` | 11 | width 32; epoch cap 80 | 14.903 | brier=0.034718 | Not opened / policy evaluation separate |
| `model-83932cca38da40a2b30c9024` | ridge | `dataset-2b612fa4cfab325eebc061f3` | 11 | Linear regression | 0.173 | rmse=0.162406, mae=0.0987557 | Not opened / policy evaluation separate |
| `model-8b05e3b3a9a24008981398e6` | ppo | `dataset-38ec6e9776097d8e36693372` | 7 | width 32; transition cap 2048 | 53.616 | See artifact / policy evaluation | Not opened / policy evaluation separate |
| `model-9474cee818f04c77962966d8` | logistic | `dataset-c6247f1456257066f0fe8d5f` | 11 | Linear classifier | 0.075 | brier=0.1434 | Not opened / policy evaluation separate |
| `model-9ba0fed73f464d84ad51341f` | cost_mlp | `dataset-2b612fa4cfab325eebc061f3` | 29 | width 32; epoch cap 80 | 15.661 | rmse=0.0973855, mae=0.0649953 | Not opened / policy evaluation separate |
| `model-a3e01a232be447e0b5702bb8` | logistic | `dataset-d8c1593a2d281e1c9e430952` | 29 | Linear classifier | 0.068 | brier=0.0364086 | Not opened / policy evaluation separate |
| `model-a7f99c63bd4f4cd4b22c57c6` | cost_mlp | `dataset-b5c3dbdac9284f292a949b65` | 29 | width 32; epoch cap 80 | 15.912 | rmse=0.112018, mae=0.0724268 | Recorded |
| `model-ab72b059dd4e4822bb91f7e2` | mlp | `dataset-d8c1593a2d281e1c9e430952` | 29 | width 32; epoch cap 80 | 14.242 | brier=0.0511194 | Not opened / policy evaluation separate |
| `model-bacc8c6876c3499a8b2ba9b0` | logistic | `dataset-d8c1593a2d281e1c9e430952` | 11 | Linear classifier | 0.063 | brier=0.0776202 | Not opened / policy evaluation separate |
| `model-c5bcd499446147838bad7a17` | logistic | `dataset-f53981b7dd24c1521ce749b1` | 11 | Linear classifier | 0.075 | brier=0.0913249 | Not opened / policy evaluation separate |
| `model-cfe981f8ce0e48408fdf7866` | mlp | `dataset-d8c1593a2d281e1c9e430952` | 29 | width 32; epoch cap 80 | 9.631 | brier=0.0344976 | Not opened / policy evaluation separate |
| `model-d085fe2fe8e443b580285509` | ridge | `dataset-b5c3dbdac9284f292a949b65` | 11 | Linear regression | 0.171 | rmse=0.139821, mae=0.102049 | Not opened / policy evaluation separate |
| `model-d3abc499a0de4eb98ff14ee2` | mlp | `dataset-f53981b7dd24c1521ce749b1` | 29 | width 32; epoch cap 80 | 12.511 | brier=0.0893766 | Not opened / policy evaluation separate |
| `model-d3dfdcb53b274a898600d5fb` | mlp | `dataset-d8c1593a2d281e1c9e430952` | 11 | width 32; epoch cap 80 | 14.269 | brier=0.0516356 | Not opened / policy evaluation separate |
| `model-d899f989b3af41e984e9afde` | mlp | `dataset-d8c1593a2d281e1c9e430952` | 29 | width 32; epoch cap 80 | 11.073 | brier=0.204694 | Not opened / policy evaluation separate |
| `model-d8f337441e3c45d48ac63670` | logistic | `dataset-d8c1593a2d281e1c9e430952` | 29 | Linear classifier | 0.064 | brier=0.207456 | Not opened / policy evaluation separate |
| `model-e8ea85c7e7fe49f7a0a2a7b9` | logistic | `dataset-d8c1593a2d281e1c9e430952` | 11 | Linear classifier | 0.066 | brier=0.0364086 | Not opened / policy evaluation separate |
| `model-ef77bbbd7d1f4be78c41c0b6` | logistic | `dataset-38ec6e9776097d8e36693372` | 11 | Linear classifier | 0.073 | brier=0.0315398 | Not opened / policy evaluation separate |
| `model-f51ed0dcc4094f2d9cbae2f2` | tree | `dataset-38ec6e9776097d8e36693372` | 7 | Decision tree | 0.047 | brier=0.0320736 | Recorded |
| `model-f587b98d06f34441bb040877` | mlp | `dataset-38ec6e9776097d8e36693372` | 7 | width 32; epoch cap 80 | 3.353 | brier=0.0289572 | Recorded |
| `model-fe2d275e53ae4295adf5ab1f` | mlp | `dataset-38ec6e9776097d8e36693372` | 11 | width 32; epoch cap 80 | 10.018 | brier=0.0291531 | Not opened / policy evaluation separate |
| `model-ff1c8c8a580944778d3eb7c0` | constant | `dataset-38ec6e9776097d8e36693372` | 7 | Fitted base rate | 0.039 | brier=0.237299 | Recorded |

PPO parent/child artifacts share a training lineage; optimizer continuation is not an independent seed. The heuristic is not fitted. A fitted constant is a baseline, not a neural model. Missing prediction-test metrics do not mean missing independent policy studies; those records are separate. No test was opened for this inventory.
