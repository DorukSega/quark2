#!/usr/bin/env python
import json
import glob
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import argparse
from datetime import datetime

class BenchmarkAnalyzer:
    def __init__(self, output_dir=None):
        self.output_dir = output_dir
        
    def _save_or_show(self, filename):
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)
            plt.savefig(os.path.join(self.output_dir, filename), dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def _normalize_duration(self, duration):
        return duration / 1e9 if duration > 1e9 else duration
    
    def _get_patterns_and_values(self, result, metric):
        patterns = [r['pattern'] for r in result['results']]
        values = [r[metric] for r in result['results']]
        if metric == 'duration':
            values = [self._normalize_duration(v) for v in values]
        return patterns, values
    
    def plot_throughput_comparison(self, results, metric):
        plt.figure(figsize=(14, 10))
        
        num_benchmarks = len(results)
        num_patterns = len(results[0]['results'])
        bar_width = 0.8 / num_benchmarks
        index = np.arange(num_patterns)
        
        for i, result in enumerate(results):
            patterns, values = self._get_patterns_and_values(result, metric)
            pos = index - 0.4 + (i + 0.5) * bar_width
            plt.bar(pos, values, bar_width, label=result['label'])
        
        self._setup_plot_labels(metric, patterns)
        plt.legend(fontsize=14)
        self._save_or_show(f'comparison_{metric}.png')
    
    def plot_relative_performance(self, results, reference_index=0, metric='mbytes_per_sec'):
        plt.figure(figsize=(14, 10))
        
        reference = results[reference_index]
        plot_results = [r for i, r in enumerate(results) if i != reference_index]
        
        if not plot_results:
            return
        
        bar_width = 0.8 / len(plot_results)
        index = np.arange(len(reference['results']))
        
        for i, result in enumerate(plot_results):
            patterns, _ = self._get_patterns_and_values(reference, metric)
            relative_values = self._calculate_relative_performance(reference, result, metric)
            
            pos = index - 0.4 + (i + 0.5) * bar_width if len(plot_results) > 1 else index
            colors = ['green' if v >= 0 else 'red' for v in relative_values]
            plt.bar(pos, relative_values, bar_width, label=result['label'], color=colors)
        
        plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        plt.ylabel('Relative Performance (%)', fontsize=16)
        plt.title(f'Performance Relative to {reference["label"]} - {metric}', fontsize=18)
        plt.xticks(index, patterns, rotation=45, fontsize=14)
        plt.yticks(fontsize=14)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.legend(fontsize=14)
        plt.gca().yaxis.set_major_formatter(FormatStrFormatter('%.1f%%'))
        plt.tight_layout()
        
        self._save_or_show(f'relative_{metric}.png')
    
    def plot_pattern_breakdown(self, results):
        plt.figure(figsize=(12, 8))
        
        for i, result in enumerate(results):
            plt.subplot(1, len(results), i+1)
            patterns, durations = self._get_patterns_and_values(result, 'duration')
            
            plt.pie(durations, labels=patterns, autopct='%1.1f%%', 
                    startangle=90, shadow=True, textprops={'fontsize': 12})
            plt.axis('equal')
            plt.title(f'Time Distribution - {result["label"]}', fontsize=16)
        
        plt.tight_layout()
        self._save_or_show('pattern_breakdown.png')
    
    def _calculate_relative_performance(self, reference, result, metric):
        relative_values = []
        for i, ref_res in enumerate(reference['results']):
            ref_value = ref_res[metric]
            result_value = result['results'][i][metric]
            relative = (result_value / ref_value - 1) * 100 if ref_value > 0 else 0
            relative_values.append(relative)
        return relative_values
    
    def _setup_plot_labels(self, metric, patterns):
        ylabel_map = {
            'mbytes_per_sec': 'Throughput (MB/s)',
            'reads_per_sec': 'Files per second',
            'duration': 'Duration (seconds)'
        }
        
        plt.ylabel(ylabel_map.get(metric, metric), fontsize=16)
        plt.title(f'Benchmark Comparison by Access Pattern - {metric}', fontsize=18)
        plt.xticks(np.arange(len(patterns)), patterns, rotation=45, fontsize=14)
        plt.yticks(fontsize=14)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
    
    def generate_summary_report(self, results, output_file=None):
        summary = [
            "# Benchmark Results Summary\n",
            f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        ]
        
        for result in results:
            summary.extend(self._format_result_summary(result))
        
        if output_file:
            with open(output_file, 'w') as f:
                f.writelines(summary)
            print(f"Summary report written to {output_file}")
        else:
            print(''.join(summary))
    
    def _format_result_summary(self, result):
        summary = [f"\n## {result['label']}\n"]
        
        if 'system' in result:
            summary.append("### System Information\n")
            summary.extend(f"- {key}: {value}\n" for key, value in result['system'].items())
        
        summary.append("\n### Configuration\n")
        for key, value in result['config'].items():
            if key == 'readPatterns':
                summary.append(f"- {key}: {', '.join(str(p) for p in value)}\n")
            else:
                summary.append(f"- {key}: {value}\n")
        
        summary.append("\n### Performance Results\n")
        summary.append("| Pattern | Duration (s) | MB/s | Files/s |\n")
        summary.append("|---------|--------------|------|--------|\n")
        
        for r in result['results']:
            duration = self._normalize_duration(r['duration'])
            summary.append(f"| {r['pattern']} | {duration:.4f} | {r['mbytes_per_sec']:.2f} | {r['reads_per_sec']:.2f} |\n")
        
        return summary

def load_benchmark_results(file_path):
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None

def load_multiple_results(patterns):
    result_files = []
    for pattern in patterns:
        files = glob.glob(pattern)
        if not files:
            print(f"Warning: No files found matching pattern '{pattern}'")
        result_files.extend(files)
    
    if not result_files:
        print("No result files found. Exiting.")
        sys.exit(1)
    
    print(f"Loading {len(result_files)} result files: {', '.join(result_files)}")
    
    results = []
    for file_path in result_files:
        result = load_benchmark_results(file_path)
        if result:
            result['label'] = result.get('label', os.path.basename(file_path).replace('.json', ''))
            results.append(result)
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Analyze and visualize benchmark results')
    parser.add_argument('files', nargs='+', help='JSON result files or glob patterns')
    parser.add_argument('-output-dir', '-o', help='Directory to save plots')
    parser.add_argument('-summary', '-s', help='Generate summary report to specified file')
    parser.add_argument('-reference', '-r', type=int, default=0, 
                        help='Index of reference result for relative comparison (default: 0)')
    
    args = parser.parse_args()
    
    results = load_multiple_results(args.files)
    
    if not results:
        print("No valid benchmark results found.")
        sys.exit(1)
    
    analyzer = BenchmarkAnalyzer(args.output_dir)
    
    for metric in ['mbytes_per_sec', 'reads_per_sec', 'duration']:
        analyzer.plot_throughput_comparison(results, metric)
    
    if len(results) > 1:
        analyzer.plot_relative_performance(results, args.reference)
    
    analyzer.plot_pattern_breakdown(results)
    
    if args.summary:
        analyzer.generate_summary_report(results, args.summary)

if __name__ == "__main__":
    main()
