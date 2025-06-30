# Photosort Roadmap: Enhanced Duplicate Detection Safety

## Overview

This roadmap addresses critical data loss scenarios identified in the duplicate detection logic of PhotoSorter, particularly around premature source file deletion and race conditions in file verification.

## Critical Data Loss Scenarios Identified

### 1. Premature Source File Deletion
**Location**: `photosort/core.py:301-308` in `_process_single_file()`
**Risk**: Source file deleted immediately after duplicate detection, before destination file integrity is verified
**Impact**: Permanent data loss if destination becomes corrupted or inaccessible

### 2. Race Conditions in Duplicate Detection  
**Location**: `photosort/core.py:144-157` in `is_duplicate()`
**Risk**: Destination file could be deleted by another process between existence check and hash comparison
**Impact**: False duplicate detection leading to data loss

### 3. Insufficient Hash Verification
**Location**: `photosort/core.py:154-157` 
**Risk**: Large files (>10MB) skip hash verification, relying only on size comparison
**Impact**: False duplicates could cause data loss

## Implementation Plan

### Phase 1: Critical Safety Fixes

#### 1.1 Implement Atomic Duplicate Handling
- **Defer source file deletion** until destination is verified
- Add destination file integrity checks before source deletion
- Implement file locking during duplicate detection
- **Files affected**: `photosort/core.py`
- **Methods**: `_process_single_file()`, `is_duplicate()`

#### 1.2 Enhanced Duplicate Verification
- Always perform hash comparison for files under 100MB (increase from 10MB)
- Add configurable hash verification threshold
- Implement progressive verification (size → hash → metadata comparison)
- **Files affected**: `photosort/core.py`, `photosort/config.py`
- **Methods**: `is_duplicate()`, `_files_have_same_hash()`

### Phase 2: Robust Error Handling

#### 2.1 Add Transaction-like Semantics
- Create backup/rollback mechanism for failed operations
- Implement staged operations with commit/abort pattern
- Add recovery from partial failures
- **New files**: `photosort/transactions.py`
- **Files affected**: `photosort/core.py`

#### 2.2 Improve Conflict Resolution
- Add safeguards against infinite loops in filename conflicts
- Implement better duplicate detection for numbered variants (`_001`, `_002`)
- Add user confirmation for ambiguous duplicate cases
- **Files affected**: `photosort/core.py`
- **Methods**: `get_destination_path()`

### Phase 3: Advanced Safety Features

#### 3.1 Add Comprehensive Verification
- Post-operation file integrity verification using checksums
- Destination file accessibility checks (read/write permissions)
- Implement file quarantine before deletion
- **New files**: `photosort/verification.py`
- **Files affected**: `photosort/core.py`

#### 3.2 Enhanced Logging and Audit Trail
- Add pre-deletion verification logs
- Implement detailed duplicate decision logging
- Add operation replay/undo functionality
- **Files affected**: `photosort/history.py`, `photosort/core.py`

### Phase 4: Testing and Validation

#### 4.1 Create Comprehensive Test Suite
- Unit tests for edge cases in duplicate detection
- Integration tests for race conditions
- Stress tests with concurrent file operations
- Mock tests for filesystem error scenarios
- **New files**: `tests/test_duplicate_safety.py`, `tests/test_race_conditions.py`

#### 4.2 Performance Testing
- Benchmark hash verification performance at different thresholds
- Test memory usage with large file collections
- Validate transaction overhead impact
- **New files**: `tests/test_performance.py`

## Configuration Enhancements

### New Configuration Options
Add to `photosort/config.py` and `~/.photosort/config.yml`:

```yaml
safety:
  hash_verification_threshold: 104857600  # 100MB
  require_destination_verification: true
  enable_file_quarantine: true
  max_filename_conflicts: 1000

duplicate_detection:
  strict_mode: false  # Require hash verification for all files
  interactive_mode: false  # Prompt for ambiguous duplicates
  backup_before_delete: true
```

## Backward Compatibility

- All safety enhancements will be opt-in initially
- Existing configuration files will continue to work
- Default behavior maintains current functionality
- New safety features can be enabled via CLI flags or config

## Success Metrics

1. **Zero data loss scenarios** in comprehensive test suite
2. **Sub-second verification** for files under 100MB
3. **< 5% performance degradation** from safety enhancements
4. **100% recovery rate** from interrupted operations
5. **Comprehensive audit trail** for all file operations

## Migration Strategy

### Phase 1 (Critical Safety) - Target: Immediate
Focus on preventing data loss in current usage patterns

### Phase 2 (Error Handling) - Target: 1-2 weeks
Add robustness without breaking existing workflows

### Phase 3 (Advanced Features) - Target: 1 month
Enhance capabilities for power users and enterprise use

### Phase 4 (Testing) - Target: Ongoing
Continuous improvement and validation

## Risk Mitigation

- **Feature flags** for all new safety mechanisms
- **Comprehensive backup strategy** during development
- **Staged rollout** to minimize impact
- **Performance monitoring** to detect regressions
- **User feedback loop** for real-world validation

---

*This roadmap prioritizes data safety while maintaining the tool's usability and performance characteristics. Each phase builds upon the previous to create a robust, enterprise-ready photo organization tool.*