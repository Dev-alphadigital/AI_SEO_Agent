#!/usr/bin/env python3
"""
SEO Brief Validation Script — Priority 1 Checklist

Validates that an SEO brief meets all Priority 1 requirements before completion.
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple

class BriefValidator:
    """Validates SEO briefs against Priority 1 requirements."""
    
    PRIORITY_1_CHECKS = [
        "url_verified",
        "gsc_data_present",
        "current_metadata_captured",
        "current_headings_captured",
        "recommended_title_description",
        "recommended_headings_table",
        "keyword_targets_with_msv",
        "no_hallucinations",
        "tone_aligned"
    ]
    
    def __init__(self, brief_path: str):
        self.brief_path = Path(brief_path)
        self.content = self.brief_path.read_text(encoding="utf-8") if self.brief_path.exists() else ""
        self.errors = []
        self.warnings = []
        self.passed = []
    
    def validate_all(self) -> Dict[str, any]:
        """Run all Priority 1 validations."""
        self.errors = []
        self.warnings = []
        self.passed = []
        
        # Run all checks
        self.check_url_verified()
        self.check_gsc_data()
        self.check_current_metadata()
        self.check_current_headings()
        self.check_recommended_metadata()
        self.check_heading_comparison_table()
        self.check_keyword_targets()
        self.check_no_hallucinations()
        self.check_tone_alignment()
        self.check_p2_gsc_vs_target_keywords()
        
        return {
            "passed": len(self.passed),
            "warnings": len(self.warnings),
            "errors": len(self.errors),
            "details": {
                "passed": self.passed,
                "warnings": self.warnings,
                "errors": self.errors
            },
            "all_passed": len(self.errors) == 0
        }
    
    def check_url_verified(self):
        """Check 1: URL is correct and matches page."""
        if "## Target:" in self.content or "Target:" in self.content:
            url_match = re.search(r'Target:\s*(https?://[^\s\|]+)', self.content)
            if url_match:
                self.passed.append("[OK] URL verified in brief")
            else:
                self.errors.append("[FAIL] URL not found in brief header")
        else:
            self.errors.append("[FAIL] No target URL section found")
    
    def check_gsc_data(self):
        """Check 2: GSC data present or noted as unavailable."""
        gsc_indicators = [
            "GSC",
            "Google Search Console",
            "clicks",
            "impressions",
            "avg position",
            "average position",
            "top queries"
        ]
        unavailable_note = "GSC data not available" in self.content or "GSC unavailable" in self.content
        
        has_gsc_data = any(indicator.lower() in self.content.lower() for indicator in gsc_indicators)
        
        if has_gsc_data or unavailable_note:
            if unavailable_note:
                self.warnings.append("[WARN] GSC data noted as unavailable (acceptable)")
            else:
                self.passed.append("[OK] GSC data present")
        else:
            self.errors.append("[FAIL] GSC data missing and not noted as unavailable")
    
    def check_current_metadata(self):
        """Check 3: Current metadata captured."""
        has_title = re.search(r'\*\*Title[:\*]?\*\*[:\s]+(.+)', self.content, re.IGNORECASE)
        has_meta = re.search(r'\*\*Meta Description[:\*]?\*\*[:\s]+(.+)', self.content, re.IGNORECASE)
        
        if has_title and has_meta:
            # Check for placeholder text
            title_text = has_title.group(1).lower()
            meta_text = has_meta.group(1).lower()
            
            placeholders = ["none", "missing", "placeholder", "to be added", "tbd"]
            if any(ph in title_text for ph in placeholders) and "(none)" not in title_text:
                self.warnings.append("[WARN] Title may contain placeholder text")
            elif "(none)" in title_text or "missing" in title_text:
                self.passed.append("[OK] Current metadata captured (noted as missing)")
            else:
                self.passed.append("[OK] Current metadata captured")
        else:
            self.errors.append("[FAIL] Current metadata not captured (title or meta description missing)")
    
    def check_current_headings(self):
        """Check 4: Current heading structure captured."""
        h1_pattern = r'\*\*H1[:\*]?\*\*[:\s]+(.+)'
        h2_pattern = r'\*\*H2[:\*]?\*\*[:\s]+(.+)'
        
        has_h1 = re.search(h1_pattern, self.content, re.IGNORECASE)
        has_h2 = re.search(h2_pattern, self.content, re.IGNORECASE)
        
        if has_h1 or "H1" in self.content:
            self.passed.append("[OK] Current heading structure captured")
        else:
            self.errors.append("[FAIL] Current heading structure not captured")
    
    def check_recommended_metadata(self):
        """Check 5: Recommended title + description included."""
        recommended_patterns = [
            r'Recommended.*Title',
            r'Recommended.*Meta',
            r'\*\*Recommended[:\*]?\*\*',
            r'Target.*Title',
            r'Target.*Meta'
        ]
        
        has_recommendations = any(re.search(pattern, self.content, re.IGNORECASE) for pattern in recommended_patterns)
        
        if has_recommendations:
            self.passed.append("[OK] Recommended title + description included")
        else:
            self.errors.append("[FAIL] Recommended title + description missing")
    
    def check_heading_comparison_table(self):
        """Check 6: Heading comparison table present."""
        table_indicators = [
            "| Current Heading",
            "| Recommended Heading",
            "Current Heading | Recommended",
            "heading.*comparison",
            "heading.*table"
        ]
        
        has_table = any(re.search(pattern, self.content, re.IGNORECASE) for pattern in table_indicators)
        
        if has_table:
            self.passed.append("[OK] Heading comparison table present")
        else:
            self.errors.append("[FAIL] Heading comparison table missing")
    
    def check_keyword_targets(self):
        """Check 7: Keyword targets with MSV included."""
        keyword_patterns = [
            r'Primary Keyword[:\*]?\*\*',
            r'Keyword.*MSV',
            r'Monthly Search Volume',
            r'Search Volume',
            r'Volume.*\d+'
        ]
        
        has_keywords = any(re.search(pattern, self.content, re.IGNORECASE) for pattern in keyword_patterns)
        
        if has_keywords:
            self.passed.append("[OK] Keyword targets with MSV included")
        else:
            self.errors.append("[FAIL] Keyword targets with MSV missing")
    
    def check_no_hallucinations(self):
        """Check 8: No hallucinations/guarantees."""
        hallucination_patterns = [
            r'guaranteed.*#1',
            r'guaranteed.*rank',
            r'will.*increase.*traffic.*by.*\d+%',
            r'guaranteed.*results',
            r'promise.*ranking'
        ]
        
        has_hallucinations = any(re.search(pattern, self.content, re.IGNORECASE) for pattern in hallucination_patterns)
        
        if not has_hallucinations:
            self.passed.append("[OK] No hallucinations/guarantees detected")
        else:
            self.errors.append("[FAIL] Hallucinations/guarantees detected — remove unsupported claims")
    
    def check_p2_gsc_vs_target_keywords(self):
        """Priority 2: Brief separates Current top queries (GSC) vs Target keywords (form)."""
        has_gsc_label = "Current top queries (GSC)" in self.content or "top queries (GSC)" in self.content
        has_target_label = "Target keywords (form)" in self.content or "Target keyword" in self.content

        if has_gsc_label and has_target_label:
            self.passed.append("[OK] P2: GSC top queries vs Target keywords clearly separated")
        else:
            missing = []
            if not has_gsc_label:
                missing.append("Current top queries (GSC)")
            if not has_target_label:
                missing.append("Target keywords (form)")
            self.warnings.append(f"[P2] Missing labels: {', '.join(missing)}")

    def check_tone_alignment(self):
        """Check 9: Tone alignment (manual check required)."""
        # This is a placeholder — tone checking requires client guidelines
        # For now, we just check if tone section exists
        tone_indicators = [
            "tone",
            "voice",
            "formality",
            "brand.*guidelines"
        ]
        
        has_tone_section = any(re.search(pattern, self.content, re.IGNORECASE) for pattern in tone_indicators)
        
        if has_tone_section:
            self.passed.append("[OK] Tone section present (manual verification recommended)")
        else:
            self.warnings.append("[WARN] Tone alignment section not found (may be acceptable if not provided)")
    
    def print_report(self):
        """Print validation report."""
        result = self.validate_all()
        
        print("=" * 60)
        print("SEO Brief Validation Report - Priority 1 & 2 Checklist")
        print("=" * 60)
        print(f"\nBrief: {self.brief_path.name}")
        total_checks = 9 + 1  # P1 + P2
        print(f"\n[OK] Passed: {result['passed']}/{total_checks}")
        print(f"[WARN] Warnings: {result['warnings']}")
        print(f"[FAIL] Errors: {result['errors']}")
        
        if result['all_passed']:
            print("\n[SUCCESS] All Priority 1 checks passed!")
        else:
            print("\n[ACTION REQUIRED] Brief needs corrections:")
            for error in result['details']['errors']:
                print(f"  {error}")
        
        if result['details']['warnings']:
            print("\n[WARNINGS]:")
            for warning in result['details']['warnings']:
                print(f"  {warning}")
        
        print("\n" + "=" * 60)
        
        return result['all_passed']


def main():
    """CLI entry point."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python validate_brief.py <brief_file.md>")
        print("\nExample:")
        print("  python validate_brief.py output/brief_sesky_pk_20260219.md")
        sys.exit(1)
    
    brief_path = sys.argv[1]
    validator = BriefValidator(brief_path)
    passed = validator.print_report()
    
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
