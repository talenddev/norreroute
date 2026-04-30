# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - 2026-04-30

### Added

- Core `Client` interface with async and sync support
- Anthropic provider integration
- Ollama provider integration
- Streaming support with `TextDelta` and `StreamEnd` events
- Tool calling support for Anthropic and Ollama
- Provider registry for custom provider registration
- Comprehensive error types (AuthenticationError, ConfigurationError, ProviderError, RateLimitError, TimeoutError_)
- Domain model dataclasses and error hierarchy
- GitHub Actions CI/CD workflows for lint, test, and build

### Fixed

- CI/CD configuration fixes
