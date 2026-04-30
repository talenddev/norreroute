# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Core `Client` interface with async and sync support
- Anthropic provider integration
- Ollama provider integration
- Streaming support with `TextDelta` and `StreamEnd` events
- Tool calling support for Anthropic
- Provider registry for custom provider registration
- Comprehensive error types (AuthenticationError, ConfigurationError, ProviderError, RateLimitError, TimeoutError_)

### Changed

- Initial release
