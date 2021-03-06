# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Save results snapshot incrementally (for each new results entry) and allow reuse. Useful if original calculation was, for some reason, stopped or to bypass unintended re-calculations. The overhead introduced by the writing of snapshots makes this feature especially useful for CPU bound models.


## [0.1.0] - 2021-02-28
### Added
- First release
