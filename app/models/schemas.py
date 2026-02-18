"""Shared Pydantic data models for the SEO analysis pipeline."""
from pydantic import BaseModel, field_validator


class PageSEO(BaseModel):
    """On-page SEO elements extracted from a URL."""
    url: str
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    meta_description_length: int = 0
    canonical_url: str = ""
    h1: str = ""
    h2s: list[str] = []
    h3s: list[str] = []
    word_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    # Open Graph tags
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    og_type: str = ""
    # Twitter Card tags
    twitter_card: str = ""
    twitter_title: str = ""
    twitter_description: str = ""
    # Technical
    robots: str = ""
    has_viewport: bool = False
    lang: str = ""
    # Content signals
    image_count: int = 0
    images_with_alt: int = 0
    has_schema_markup: bool = False
    schema_types: list[str] = []


class AhrefsMetrics(BaseModel):
    """Domain/URL-level metrics from Ahrefs."""
    domain_rating: float = 0.0
    url_rating: float = 0.0
    backlinks: int = 0
    referring_domains: int = 0
    organic_keywords: int = 0
    organic_traffic: int = 0


class KeywordMetrics(BaseModel):
    """Keyword-level metrics from Ahrefs."""
    keyword: str
    volume: int = 0
    difficulty: int = 0
    cpc: float = 0.0
    traffic_potential: int = 0
    intent: str = ""  # informational, commercial, transactional, navigational


class SerpEntry(BaseModel):
    """A single SERP result."""
    position: int
    url: str
    title: str = ""
    domain_rating: float = 0.0


class CompetitorPage(BaseModel):
    """Combined SEO + Ahrefs data for a competitor page."""
    url: str
    page_seo: PageSEO
    ahrefs_metrics: AhrefsMetrics


class GapAnalysis(BaseModel):
    """Gaps between target page and competitors."""
    missing_topics: list[str] = []
    missing_keywords: list[str] = []
    structure_recommendations: list[str] = []
    word_count_target: int = 0
    avg_competitor_word_count: int = 0
    content_quality_issues: list[str] = []


class SEOBrief(BaseModel):
    """Complete SEO reoptimization brief — the final output."""
    target_url: str
    keyword: str
    target_page_seo: PageSEO
    ahrefs_metrics: AhrefsMetrics
    keyword_metrics: KeywordMetrics
    serp_results: list[SerpEntry] = []
    competitors: list[CompetitorPage] = []
    gap_analysis: GapAnalysis
    markdown_path: str = ""
    warnings: list[str] = []


class ReoptimizationBrief(SEOBrief):
    """SEO brief extended with AI-generated reoptimization output."""
    ai_brief: str = ""
    ai_model: str = ""
    ai_markdown_path: str = ""
