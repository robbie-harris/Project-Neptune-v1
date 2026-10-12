# MarinaPipe and Real Deployment

[[Home]] · [[Inspection Objects and Optics]] · [[Research]] · [[Ideas]]

## Deployment objective

The user clarified on 2026-10-11 that Neptune must eventually operate underwater in the real world. Simulator performance is a prototype acceptance result, not evidence of deployment readiness. Real images covering all three classes and the intended cameras, illumination, water and working distances are required for the deployment training/evaluation phase. The current simulator-only run remains a reproducible baseline and continues collecting; this clarification does not cancel it.

## MarinaPipe assessment

[Dataset record](https://zenodo.org/records/10951363), [author repository](https://github.com/remaro-network/MarinaPipe-dataset), [associated paper](https://stellagrasshof.com/assets/pdf/2024_marnet_oceans.pdf).

The author table lists seven video sequences, 1,723 selected labeled frames and 199 pipe-positive frames in total. Five sequences include fine and coarse masks; sequences 5 and 6 have coarse masks only. These totals are calculated from published metadata, not an audited downloaded archive. The data shows real seabed pipes, underwater appearance and partial occlusions. The GoPro-on-LAUV imagery and cropped pipeline-following views differ from Neptune's current forward inspection camera. No valve/flange annotations are provided.

The masks were produced for cropped images. Match each mask to its actual cropped image; never resize a mask onto an uncropped original without a verified coordinate transform. Fine masks can provide visible-pipe boxes using existing OpenCV routines, but disconnected/overlapping pipe regions require instance review. Coarse boxes require a separate audit. Review apparent negatives for every target class before treating them as three-class background. Never turn missing annotations into negatives.

## License verification

A read-only request to [Zenodo record metadata](https://zenodo.org/api/records/10951363) returned title MarinaPipe, access_right open, and license.id **cc-by-4.0**. The repository lists MIT, but the actual archive's Zenodo metadata supplies the data license. Preserve source attribution, the paper citation and OceanScan-MST collection acknowledgement requested by the authors. Public import has not occurred; prior upload authorization was simulator-only. Archive size is 27.8 GB according to Zenodo. No archive was downloaded during this assessment.

## Proposed real-image phase

1. Evaluate the simulator baseline on audited MarinaPipe frames as an initial transfer diagnostic before using those frames for training.
2. Freeze sequence-wise train/validation/test partitions with sufficient positives, near-duplicate checks and source hashes. Whole videos stay in one split; original and cropped copies stay together. Adjacent frames must not leak between partitions. Seven sequences from one marina do not establish generalization to new deployment sites.
3. Fine-tune a separate candidate on simulator data plus selected real pipe images; retain simulator valve/flange examples to reduce forgetting. Compare against simulator-only on untouched real sequences and the existing simulator tests.
4. Collect and annotate real valves and bolted flanges, alongside pipes, using Neptune's intended camera/lamp geometry. Include clear/turbid water, lamp-only operation, approach angles, partial views and genuine non-target structures. Audit all three classes in every selected training image.
5. Maintain an untouched real deployment test set from separate dives/sites where possible. Report per-class recall, false positives, small targets, illumination/water slices and live latency. Real accuracy is currently **unmeasured**.

MarinaPipe is recommended as a pipe-focused real-data supplement and transfer benchmark. It cannot replace the multiclass simulator dataset or establish real valve/flange accuracy. The associated paper's synthetic-pretraining/real-fine-tuning results concern SegFormer segmentation and are not a YOLO11n performance guarantee.
