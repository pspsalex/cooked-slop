# Changelog

## [0.3.1](https://github.com/pspsalex/cooked-slop/compare/cooked-slop-v0.3.0...cooked-slop-v0.3.1) (2026-10-04)


### Bug Fixes

* **core:** resolve batch conversion hang, false two-col detections, and text/PRN parsing (SPEC-037) ([1d65d6a](https://github.com/pspsalex/cooked-slop/commit/1d65d6a535e50dc4994a13bbedbe8e311d16dd7c))

## [0.3.0](https://github.com/pspsalex/cooked-slop/compare/cooked-slop-v0.2.0...cooked-slop-v0.3.0) (2026-10-04)


### Features

* Add  test suite and various example recipe files for format conversion tests. ([fe68db2](https://github.com/pspsalex/cooked-slop/commit/fe68db2b3cc2d67f10499e2c52b4b5a2e8c17d83))
* add Bread-Bakers mailing list archive extraction script ([5974a38](https://github.com/pspsalex/cooked-slop/commit/5974a38396ef929c5a532ff62724bf7a88774f92))
* add extension-based batch conversion runner script (batch_convert.py) ([bc24c60](https://github.com/pspsalex/cooked-slop/commit/bc24c60ce2c0154755cc580bdf8008aa17934888))
* add HTML config for cs.cmu Usenet Recipe Archive ([b571bd6](https://github.com/pspsalex/cooked-slop/commit/b571bd61bb1fe13227cf67735ddcf14b7f510b00))
* add HTML config for garvick.com ([05fa33a](https://github.com/pspsalex/cooked-slop/commit/05fa33addbaba3f70c9dde5f8ab7989e3ccbdd02))
* add HTML config for macropolis ([252be3a](https://github.com/pspsalex/cooked-slop/commit/252be3acb1c4be7081d96e5cbad592eb58bd170a))
* add HTML config for mcnalley recipe collection ([5ec7ac1](https://github.com/pspsalex/cooked-slop/commit/5ec7ac1d4463ca3be660080ad033d3b2c6a9ba86))
* add HTML config for Top Secret Recipes ([61372aa](https://github.com/pspsalex/cooked-slop/commit/61372aa16c632bef95446b82a64d556e1bd8a80c))
* add HTML configs for mexican, netrelief, bbq, chile, and coffeeshop collections ([9330ec5](https://github.com/pspsalex/cooked-slop/commit/9330ec569b536052b6d2d7093aef68ec1040b92e))
* add llm parser, make html parser register, rewrite generic parser ([ed58486](https://github.com/pspsalex/cooked-slop/commit/ed58486c0a1f3dc3fa45786521e5d7a530f3d075))
* add microcook and new csv parser; update LLM files ([ecb4d19](https://github.com/pspsalex/cooked-slop/commit/ecb4d197032042cfbf25b25818bfbaa12216a326))
* add microcook support ([0b2418a](https://github.com/pspsalex/cooked-slop/commit/0b2418a19db3b82a7aceaa60523069b1eb07bb1a))
* add Schema.org JSON-LD pass-through parser (FEAT-001) ([e77532c](https://github.com/pspsalex/cooked-slop/commit/e77532cdce806857da343d0eb33d2dc746bac2c7))
* add spec-driven development framework for ToDo recipe processing ([c9ffca8](https://github.com/pspsalex/cooked-slop/commit/c9ffca8e8c67d0e381b002cc350761d37690f6d4))
* add sqlite import config file, fix sqlite import and make copilot ([3942979](https://github.com/pspsalex/cooked-slop/commit/3942979e83df91b4bbd8c86be53ebc2f1d3d8a8f))
* add url tags, more parsers, samples, stuff ([96f42c8](https://github.com/pspsalex/cooked-slop/commit/96f42c851850b5f05f5cd2216d126835c9b2be6d))
* allow multiple recipes per md ([42c702b](https://github.com/pspsalex/cooked-slop/commit/42c702b2db01335f546295713fb8ae33317652ef))
* bbc-food generic parser, fix MC categories ([d75dab8](https://github.com/pspsalex/cooked-slop/commit/d75dab8031ac1d84f6c1621e976df89e3773db94))
* **cli:** consolidate directory batch conversion into convert.py (SPEC-029) ([a0d3350](https://github.com/pspsalex/cooked-slop/commit/a0d3350321893e0b997c7f2759408a077dcb1ccc))
* **cli:** display parser and config name next to file in verbose mode ([324eef5](https://github.com/pspsalex/cooked-slop/commit/324eef50ef425bdaeafd8e7a1caf740b1a969c5c))
* **csv:** add YAML-configurable unified CSV parser (SPEC-035) ([89a7671](https://github.com/pspsalex/cooked-slop/commit/89a76714f02ea897bfe19e77477931a8fcf4ba73))
* dual column recipe parser, larger context for detection, fine tuning ([61ef489](https://github.com/pspsalex/cooked-slop/commit/61ef4897ed7aa523aa81ff41676fb529c05d562e))
* **extract:** add docling support and fix yield strip crash in vjje extractor ([e093972](https://github.com/pspsalex/cooked-slop/commit/e09397274dc42edaa3971c98b9692a80d6cc05d1))
* **extract:** add Recipe Box printer dump (.PRN) extractor ([288bfbb](https://github.com/pspsalex/cooked-slop/commit/288bfbb1f1e1bb7f3fa1249cab440930f36e3a7b))
* **extract:** add VJJE recipe collection extractor for text and scanned PDFs ([ed044ad](https://github.com/pspsalex/cooked-slop/commit/ed044add3d6d0ab10eb8ecbb9f981b585baad57d))
* **extract:** implement vintage PRN print dump normalizer (SPEC-028) ([de10c35](https://github.com/pspsalex/cooked-slop/commit/de10c35ebd6cc0c2c740ee906305e9d13add8e01))
* HTML, MD parser, some QoL improvements ([8a4fb0d](https://github.com/pspsalex/cooked-slop/commit/8a4fb0d28e9e39229605d191dc06850fcfba6230))
* **html:** add blank recipe guard and refine bbq xpath schema for blockquotes ([4d9c82c](https://github.com/pspsalex/cooked-slop/commit/4d9c82c7b2aa33fd72be0c920231de111c03cce6))
* id_caps parser ([aa7c5aa](https://github.com/pspsalex/cooked-slop/commit/aa7c5aa823af430d75519cc626c8cb0edb29267b))
* Implement Ricette recipe parser and add new test samples and expected outputs for various formats. ([ea8e267](https://github.com/pspsalex/cooked-slop/commit/ea8e2675fac3dfeab49c725fdba2f10c3d119441))
* improve MC/MM robustness; update unit normalization lut; add standlone extract helper tools ([2090e0c](https://github.com/pspsalex/cooked-slop/commit/2090e0ca6871beb20fe3550e541f18975e76c690))
* Introduce NYC, Edna, and Ricette Markdown recipe parsers, add format option ([33d361c](https://github.com/pspsalex/cooked-slop/commit/33d361ce661875b7be985d6b900683a7eeff8143))
* make llm parser add markers instead of generating json ([0963119](https://github.com/pspsalex/cooked-slop/commit/09631194fbef8021da47fe949db48bcac166b47d))
* new parsers; recipes are now output as they are extracted ([dfd76b6](https://github.com/pspsalex/cooked-slop/commit/dfd76b68f865ec6ef460e4b55927a6b1c3a3d24e))
* normalize all the units ([98cd230](https://github.com/pspsalex/cooked-slop/commit/98cd230c16bdc2342abcfe7cc47791393eb794f0))
* **packaging:** add pyproject.toml with cook CLI and reorganize tools (SPEC-019) ([994952c](https://github.com/pspsalex/cooked-slop/commit/994952c57236b10d3563dfb784c3f896d231f71b))
* **packaging:** merge SPEC-019 pyproject.toml with cook CLI and tools reorganization ([eb38d3c](https://github.com/pspsalex/cooked-slop/commit/eb38d3c8e456ba069b48f7265d556a7e8f7ebdaf))
* **parser:** add line number URL fragments to markdown parsers (SPEC-022) ([67e500e](https://github.com/pspsalex/cooked-slop/commit/67e500e569f5293ab635a4a2bf183ef1a7878ed0))
* **parser:** implement AccuChef format parser (SPEC-027) ([e8436d7](https://github.com/pspsalex/cooked-slop/commit/e8436d764c021cb3dd21a7b51aeb7ccb63734555))
* **parser:** implement Buster text format parser (SPEC-024) ([5320571](https://github.com/pspsalex/cooked-slop/commit/5320571f9a9eca0f7b21b26076def782d4bab634))
* **parser:** implement From Scratch v2.0 format parser (SPEC-010) ([f6afcb5](https://github.com/pspsalex/cooked-slop/commit/f6afcb5c81b0f3106031a56c5a2116256964542f))
* **parser:** implement Info-Mac BBS format parser (SPEC-011) ([b9981c0](https://github.com/pspsalex/cooked-slop/commit/b9981c09d8fbec227171aceb78f4575fc833fe8c))
* **parser:** implement Mr. Boston drinks database parser (SPEC-009) ([d4b1d92](https://github.com/pspsalex/cooked-slop/commit/d4b1d92ea1640dcdc6047ffca7c5427af0f67aa2))
* **parser:** implement RCP nutritional exchange format parser (SPEC-012) ([2ec2e99](https://github.com/pspsalex/cooked-slop/commit/2ec2e9930631cc9578647fb2063ddae2ce970fb5))
* **parser:** resolve generic markdown pandoc edge cases (SPEC-026) ([62c5f92](https://github.com/pspsalex/cooked-slop/commit/62c5f928274d33ece26a68058a2feb26463e4084))
* **parsers:** centralize title sanitization, yield stripping, divider filtering, and ingredient unescaping ([d059818](https://github.com/pspsalex/cooked-slop/commit/d059818e37d69353cdb74a7c65915809e8ca4a39))
* **parsers:** implement parser auto-discovery and contract hardening (SPEC-014) ([ed02256](https://github.com/pspsalex/cooked-slop/commit/ed02256d03d2f218605ddac6ce9a4fb5d094e312))
* **parsers:** merge SPEC-014 parser auto-discovery and contract hardening ([30a5fae](https://github.com/pspsalex/cooked-slop/commit/30a5faefa96861950940d693d5b0433780dcf3f3))
* **parsers:** support multi-recipe boundary splitting in two-col and generic text parsers ([1c0efd5](https://github.com/pspsalex/cooked-slop/commit/1c0efd52ee92bf0de9b05e101faf125cac96aa28))
* refactor MM import to allow proper import of dual column recipes ([c92a8a2](https://github.com/pspsalex/cooked-slop/commit/c92a8a2a95621e7a26bbc69144f6a64143e3c1b5))
* refactored for some reason ([ffefc51](https://github.com/pspsalex/cooked-slop/commit/ffefc51152be81854f0aa50d8a13b98177414058))
* **registry:** add dynamic supported_extensions and directory discovery (SPEC-017) ([f046314](https://github.com/pspsalex/cooked-slop/commit/f0463145cfa01bf4dd2c17dbc90d7e0798687b7c))
* **registry:** merge SPEC-017 dynamic supported_extensions and directory discovery ([69ed27b](https://github.com/pspsalex/cooked-slop/commit/69ed27bdb06531e3aced867573e8ee7cb0a1cfe9))
* remove date from json ([2c021ff](https://github.com/pspsalex/cooked-slop/commit/2c021ff17d99226b48fb64659f7a908988cb0f12))
* split and group generated files in hashed folders ([f81a8b5](https://github.com/pspsalex/cooked-slop/commit/f81a8b57ed40be0d78b253fdc28c0f4d4c5ffb40))


### Bug Fixes

* add missing type hints to parser __init__ and recipeml helpers (QUAL-002) ([dd08478](https://github.com/pspsalex/cooked-slop/commit/dd08478401f598d4bed23a6d41b8da44df6189fa))
* add parse_buffer() to NYCParser to prevent mixed.py AttributeError ([e982798](https://github.com/pspsalex/cooked-slop/commit/e9827982d4d041a4393dfd1700edd92560fce74e))
* **batch:** disambiguate output json paths to prevent overwriting split and numeric files ([c29445a](https://github.com/pspsalex/cooked-slop/commit/c29445a760eff5f97f1dcbfbdb638fa043876907))
* broaden yield regex in generic.py to capture full yield string ([0a58dec](https://github.com/pspsalex/cooked-slop/commit/0a58decca7083bd2ad161b13f776e714fcae9ea5))
* correct \u008d to \u200d in vitt.py _extract_instructions() ([100885e](https://github.com/pspsalex/cooked-slop/commit/100885ea722b0ea8ac66e43bc157ac2c868afb5d))
* correct parse_buffer() return type annotation in compuchef.py ([c5f3449](https://github.com/pspsalex/cooked-slop/commit/c5f34492c4dfce934599abe9367e9dd6f24cd18e))
* dynamically populate -f flag choices from ParserRegistry ([757f095](https://github.com/pspsalex/cooked-slop/commit/757f0952839a1b3509ca3befaae48fb3f0393d6c))
* extend instruction detection ([ca8afc5](https://github.com/pspsalex/cooked-slop/commit/ca8afc57348cd01c95e79d9d9db65823e3cb76fe))
* finetune html config, remove path dependence ([0047c97](https://github.com/pspsalex/cooked-slop/commit/0047c979fdb7247252a7b804c486d4cf55116254))
* **generic_md:** support bold titles, heading hierarchy, and tighten compuchef detection (SPEC-020) ([817105e](https://github.com/pspsalex/cooked-slop/commit/817105e5f523da2f5349c0627d26905101ef558d))
* improve table handling, MD recipe parsing ([6d96369](https://github.com/pspsalex/cooked-slop/commit/6d96369158b3c95e71eb81cafa5667e58e104325))
* make all tests run in the workflow ([0a18c2f](https://github.com/pspsalex/cooked-slop/commit/0a18c2f00541282b45bf6cd7ea7c051ce30d67a5))
* **parser:** improve generic markdown instruction detection (SPEC-023) ([c12d7ac](https://github.com/pspsalex/cooked-slop/commit/c12d7ac445bb4a52c82e47825d092f787744aecb))
* reduce ricette_md.py false positives with Italian keyword heuristics (FEAT-003) ([ce59e0b](https://github.com/pspsalex/cooked-slop/commit/ce59e0bf465ee191f9aada3981be1a7be1102435))
* remove SIGINT handling, add sqlite recipe parser to registry ([da4190a](https://github.com/pspsalex/cooked-slop/commit/da4190a9ffeb42506eb2a7a0291b183d42e9945d))
* replace print() with logger calls in compuchef.py and ricette_json.py ([38e79de](https://github.com/pspsalex/cooked-slop/commit/38e79de3dd1273e92267006ec5f465a871d2aeb0))
* resolve NLP ingredient parser NameError by moving import to module scope ([58ac5e0](https://github.com/pspsalex/cooked-slop/commit/58ac5e079488255661ca46b1e68f7a0a6113e4ad))
* sanitize private local paths from all tracked files ([f5c15d1](https://github.com/pspsalex/cooked-slop/commit/f5c15d1544247e905c30a14128c81c607a94aa63))
* unit normalization ([7f55e12](https://github.com/pspsalex/cooked-slop/commit/7f55e125910b7b299e959fa1350b457809cf9667))
* use sys.executable instead of bare 'python3' in test_conversion.py ([c66e505](https://github.com/pspsalex/cooked-slop/commit/c66e5057d1570eb3d5fe210a11cb07d47ba5b4a0))
* write output in convert_recipe_file() multi-recipe mode ([9c01b05](https://github.com/pspsalex/cooked-slop/commit/9c01b0530d472d22a2a4c8b22fa540962719549f))


### Performance Improvements

* optimize pytest speed via in-process execution and lazy imports ([06b447f](https://github.com/pspsalex/cooked-slop/commit/06b447f861972844f8a450e1d431181b34fb6553))
* optimize pytest speed via in-process execution and lazy imports ([ee8ddec](https://github.com/pspsalex/cooked-slop/commit/ee8ddece196805f4ae959b140d87f0a15f3a8e78))


### Refactoring

* add __init__.py to parsers/sqlite/ package (QUAL-005) ([32cc0c0](https://github.com/pspsalex/cooked-slop/commit/32cc0c0d8de76fbd17364781f0170e3ee7bc2a42))
* add module-level loggers to vitt.py and twentykrecipes.py ([eea3dd0](https://github.com/pspsalex/cooked-slop/commit/eea3dd044b082a91d710e6d1253a2e0dc192e9ac))
* add pluggable detection, SQLite parser, fix mixed formats ([1f7f5da](https://github.com/pspsalex/cooked-slop/commit/1f7f5da19d8e878243bb98c3cb1bd573a9850fe5))
* clean up parser logging and optimize SQLite query performance ([3e2c4ad](https://github.com/pspsalex/cooked-slop/commit/3e2c4ad40145d62208e2d105fde30e97787e0423))
* **cli:** reduce NLP verbosity under -v flag (SPEC-021) ([f198051](https://github.com/pspsalex/cooked-slop/commit/f198051382f1855a7a28613950e3235e6b3cfa28))
* **convert:** decompose into converter, writer, shard, and ui modules (SPEC-015) ([836c612](https://github.com/pspsalex/cooked-slop/commit/836c612a9e41762c22a7c57c4b6aca3b6bb304ad))
* **convert:** merge SPEC-015 modular conversion pipeline ([6507f4f](https://github.com/pspsalex/cooked-slop/commit/6507f4fd7a410d62fb368f8b77a7a71a206b00ab))
* **core:** organize root files, extract core pipeline, and standardize configs ([957bdf2](https://github.com/pspsalex/cooked-slop/commit/957bdf229d98cd534f116e0215a1a8cacf9258fb))
* **csv:** inline 20k helper, drop legacy aliases and superseded chefs extractor ([78b90cd](https://github.com/pspsalex/cooked-slop/commit/78b90cd9d0801754e75a9e4294c27f179d7bc2e7))
* **pipeline:** use relative paths in output JSON-LD (SPEC-025) ([32f51f3](https://github.com/pspsalex/cooked-slop/commit/32f51f34b9d5b821d70500915f415016f0ca8231))
* **registry:** drop format aliases in favor of canonical format_id ([a9b374a](https://github.com/pspsalex/cooked-slop/commit/a9b374acef82623ad94e24b1afb9e8773ea6e689))
* remove redundant imports from detect() methods and unused variable (QUAL-003, QUAL-006) ([c2d0b7d](https://github.com/pspsalex/cooked-slop/commit/c2d0b7dcb7b920e70843af762fd3a2d06028ec37))
* unify spec-driven development infrastructure into tasks.md and specs/ ([32281ef](https://github.com/pspsalex/cooked-slop/commit/32281ef27b2db4cd7bcacd97df5f3e37b9f9275d))
* **vitt:** move Vitt BBS echo parser to standalone extractor tool ([ceb8272](https://github.com/pspsalex/cooked-slop/commit/ceb8272b2c957dc2b714c9c8a41a434e920ad6d1))
