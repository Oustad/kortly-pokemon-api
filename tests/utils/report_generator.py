"""HTML report generator for accuracy testing results."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import shutil

from jinja2 import Template
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


class ReportGenerator:
    """Generate HTML reports for testing results."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate_report(
        self, 
        analysis: Dict[str, Any], 
        results: List[Dict[str, Any]],
        test_images_dir: Path
    ) -> Path:
        """
        Generate comprehensive HTML report.
        
        Args:
            analysis: Detailed analysis from StatsAnalyzer
            results: Raw test results
            test_images_dir: Directory containing test images
            
        Returns:
            Path to generated HTML report
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"accuracy_report_{timestamp}.html"
        
        # Create images directory for report
        images_dir = self.output_dir / "images"
        images_dir.mkdir(exist_ok=True)
        
        # Generate charts
        charts = self._generate_charts(analysis)
        
        # Copy sample images
        sample_images = self._prepare_sample_images(results, test_images_dir, images_dir)
        
        # Generate HTML
        html_content = self._generate_html(
            analysis=analysis,
            charts=charts,
            sample_images=sample_images,
            timestamp=timestamp
        )
        
        # Write report
        report_path.write_text(html_content, encoding='utf-8')
        
        return report_path
    
    def _generate_charts(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """Generate Plotly charts as HTML strings."""
        metrics = analysis["overall_metrics"]
        charts = {}
        
        # Success rate pie chart
        fig_success = go.Figure(data=[go.Pie(
            labels=['Successful', 'Failed'],
            values=[metrics.successful_scans, metrics.failed_scans],
            hole=0.3,
            marker_colors=['#10b981', '#ef4444']
        )])
        fig_success.update_layout(
            title="Scan Success Rate",
            height=400,
            margin=dict(t=50, b=50, l=50, r=50)
        )
        charts["success_rate"] = fig_success.to_html(include_plotlyjs='cdn', div_id="success_chart")
        
        # Processing tier distribution
        if metrics.processing_tier_distribution:
            fig_tiers = go.Figure(data=[go.Bar(
                x=list(metrics.processing_tier_distribution.keys()),
                y=list(metrics.processing_tier_distribution.values()),
                marker_color=['#10b981', '#3b82f6', '#8b5cf6']
            )])
            fig_tiers.update_layout(
                title="Processing Tier Distribution",
                xaxis_title="Processing Tier",
                yaxis_title="Number of Images",
                height=400
            )
            charts["processing_tiers"] = fig_tiers.to_html(include_plotlyjs=False, div_id="tiers_chart")
        
        # Quality score distribution
        if metrics.quality_distribution:
            fig_quality = go.Figure(data=[go.Bar(
                x=list(metrics.quality_distribution.keys()),
                y=list(metrics.quality_distribution.values()),
                marker_color='#f59e0b'
            )])
            fig_quality.update_layout(
                title="Image Quality Distribution",
                xaxis_title="Quality Category",
                yaxis_title="Number of Images",
                height=400
            )
            charts["quality_distribution"] = fig_quality.to_html(include_plotlyjs=False, div_id="quality_chart")
        
        # Timing distribution histogram
        if metrics.timing_percentiles:
            # Create timing histogram using percentile data
            fig_timing = go.Figure()
            fig_timing.add_trace(go.Scatter(
                x=['p50', 'p90', 'p95', 'p99', 'max'],
                y=[
                    metrics.timing_percentiles.get('p50', 0),
                    metrics.timing_percentiles.get('p90', 0),
                    metrics.timing_percentiles.get('p95', 0),
                    metrics.timing_percentiles.get('p99', 0),
                    metrics.timing_percentiles.get('max', 0)
                ],
                mode='lines+markers',
                name='Processing Time',
                line=dict(color='#6366f1')
            ))
            fig_timing.update_layout(
                title="Processing Time Percentiles",
                xaxis_title="Percentile",
                yaxis_title="Time (ms)",
                height=400
            )
            charts["timing_percentiles"] = fig_timing.to_html(include_plotlyjs=False, div_id="timing_chart")
        
        return charts
    
    def _prepare_sample_images(
        self, 
        results: List[Dict[str, Any]], 
        test_images_dir: Path, 
        output_images_dir: Path
    ) -> List[Dict[str, Any]]:
        """Prepare sample images for the report."""
        samples = []
        
        # Get representative samples
        successful = [r for r in results if r.get("success")]
        failed = [r for r in results if not r.get("success")]
        
        # Add up to 10 successful and 5 failed samples
        sample_results = successful[:10] + failed[:5]
        
        for result in sample_results:
            filename = result.get("filename", "unknown")
            source_path = test_images_dir / filename
            
            if source_path.exists():
                # Copy image to output directory
                dest_path = output_images_dir / filename
                try:
                    shutil.copy2(source_path, dest_path)
                    
                    samples.append({
                        "filename": filename,
                        "relative_path": f"images/{filename}",
                        "success": result.get("success", False),
                        "processing_time": result.get("_test_metadata", {}).get("request_time_ms", 0),
                        "quality_score": result.get("processing", {}).get("quality_score"),
                        "processing_tier": result.get("processing", {}).get("processing_tier"),
                        "tcg_matches": len(result.get("tcg_matches", [])),
                        "error": result.get("error"),
                        "best_match_name": result.get("best_match", {}).get("name") if result.get("best_match") else None,
                    })
                except Exception as e:
                    print(f"Warning: Could not copy {filename}: {e}")
        
        return samples
    
    def _generate_html(
        self, 
        analysis: Dict[str, Any], 
        charts: Dict[str, str],
        sample_images: List[Dict[str, Any]],
        timestamp: str
    ) -> str:
        """Generate the complete HTML report."""
        
        template_str = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pokemon Card Scanner - Accuracy Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f8fafc; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 30px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .metric-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .metric-value { font-size: 2rem; font-weight: bold; color: #1f2937; }
        .metric-label { color: #6b7280; font-size: 0.9rem; margin-top: 5px; }
        .chart-section { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .samples-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .sample-card { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .sample-image { width: 100%; height: 200px; object-fit: cover; }
        .sample-info { padding: 15px; }
        .success { border-left: 4px solid #10b981; }
        .failed { border-left: 4px solid #ef4444; }
        .status-badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 500; }
        .status-success { background: #d1fae5; color: #065f46; }
        .status-failed { background: #fee2e2; color: #991b1b; }
        .tier-fast { color: #10b981; }
        .tier-standard { color: #3b82f6; }
        .tier-enhanced { color: #8b5cf6; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #f9fafb; font-weight: 600; }
        .error-list { max-height: 300px; overflow-y: auto; background: #fef2f2; padding: 15px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🃏 Pokemon Card Scanner - Accuracy Report</h1>
            <p>Generated: {{ timestamp }}</p>
            <p>Total Images Tested: <strong>{{ analysis.overall_metrics.total_images }}</strong></p>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value" style="color: #10b981;">{{ "%.1f"|format(analysis.overall_metrics.success_rate) }}%</div>
                <div class="metric-label">Success Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{{ "%.0f"|format(analysis.overall_metrics.avg_processing_time) }}ms</div>
                <div class="metric-label">Avg Processing Time</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${{ "%.4f"|format(analysis.overall_metrics.total_cost) }}</div>
                <div class="metric-label">Total API Cost</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${{ "%.6f"|format(analysis.overall_metrics.avg_cost_per_scan) }}</div>
                <div class="metric-label">Avg Cost Per Scan</div>
            </div>
        </div>
        
        {% if charts.success_rate %}
        <div class="chart-section">
            {{ charts.success_rate|safe }}
        </div>
        {% endif %}
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
            {% if charts.processing_tiers %}
            <div class="chart-section">
                {{ charts.processing_tiers|safe }}
            </div>
            {% endif %}
            
            {% if charts.quality_distribution %}
            <div class="chart-section">
                {{ charts.quality_distribution|safe }}
            </div>
            {% endif %}
        </div>
        
        {% if charts.timing_percentiles %}
        <div class="chart-section">
            {{ charts.timing_percentiles|safe }}
        </div>
        {% endif %}
        
        <div class="chart-section">
            <h3>📊 Detailed Statistics</h3>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Images Processed</td>
                    <td>{{ analysis.overall_metrics.total_images }}</td>
                </tr>
                <tr>
                    <td>Successful Scans</td>
                    <td>{{ analysis.overall_metrics.successful_scans }}</td>
                </tr>
                <tr>
                    <td>Failed Scans</td>
                    <td>{{ analysis.overall_metrics.failed_scans }}</td>
                </tr>
                <tr>
                    <td>TCG Match Success Rate</td>
                    <td>{{ "%.1f"|format(analysis.tcg_analysis.match_success_rate) }}%</td>
                </tr>
                <tr>
                    <td>Translations Performed</td>
                    <td>{{ analysis.language_analysis.translations_performed }} ({{ "%.1f"|format(analysis.language_analysis.translation_rate) }}%)</td>
                </tr>
            </table>
        </div>
        
        {% if analysis.failed_scans %}
        <div class="chart-section">
            <h3>❌ Failed Scans</h3>
            <div class="error-list">
                {% for failed in analysis.failed_scans %}
                <div style="margin-bottom: 10px; padding: 10px; background: white; border-radius: 4px;">
                    <strong>{{ failed.filename }}</strong><br>
                    <span style="color: #ef4444;">{{ failed.error }}</span>
                    <span style="color: #6b7280;">(Status: {{ failed.status_code }})</span>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
        
        <div class="chart-section">
            <h3>🖼️ Sample Results</h3>
            <div class="samples-grid">
                {% for sample in sample_images %}
                <div class="sample-card {{ 'success' if sample.success else 'failed' }}">
                    <img src="{{ sample.relative_path }}" alt="{{ sample.filename }}" class="sample-image" onerror="this.style.display='none'">
                    <div class="sample-info">
                        <div style="margin-bottom: 10px;">
                            <strong>{{ sample.filename }}</strong>
                            <span class="status-badge {{ 'status-success' if sample.success else 'status-failed' }}">
                                {{ 'SUCCESS' if sample.success else 'FAILED' }}
                            </span>
                        </div>
                        {% if sample.success %}
                            <div>Time: {{ "%.0f"|format(sample.processing_time) }}ms</div>
                            <div>Quality: {{ "%.0f"|format(sample.quality_score or 0) }}/100</div>
                            <div>Tier: <span class="tier-{{ sample.processing_tier }}">{{ sample.processing_tier|upper }}</span></div>
                            <div>TCG Matches: {{ sample.tcg_matches }}</div>
                            {% if sample.best_match_name %}
                            <div>Best Match: {{ sample.best_match_name }}</div>
                            {% endif %}
                        {% else %}
                            <div style="color: #ef4444;">{{ sample.error }}</div>
                        {% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
</body>
</html>
        """
        
        template = Template(template_str)
        return template.render(
            analysis=analysis,
            charts=charts,
            sample_images=sample_images,
            timestamp=timestamp
        )