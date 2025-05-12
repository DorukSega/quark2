#!/usr/bin/env python3

import argparse
import json
import os
import random
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any
import socket

@dataclass
class Config:
    num_files: int = 100
    file_size_kb: int = 1024
    patterns: List[int] = None
    target_dir: str = "benchmark_files"
    iterations: int = 5
    
    def __post_init__(self):
        if self.patterns is None:
            self.patterns = [1, 2, 3, 4, 5, 6]

@dataclass
class Result:
    pattern: str
    duration: float
    file_count: int
    bytes_read: int
    reads_per_sec: float
    mbytes_per_sec: float

class Benchmark:
    PATTERNS = {
        1: "Sequential",
        2: "Reverse Sequential", 
        3: "Random",
        4: "Zipfian",
        5: "Locality-Based",
        6: "Repeated Access"
    }
    
    def __init__(self, config: Config):
        self.config = config
        self.files = []
        
    def create_files(self):
        os.makedirs(self.config.target_dir, exist_ok=True)
        size = self.config.file_size_kb * 1024
        
        for i in range(self.config.num_files):
            path = Path(self.config.target_dir) / f"test_file_{i:04d}.dat"
            with open(path, 'wb') as f:
                f.write(os.urandom(size))
            self.files.append(path)
            
    def get_access_pattern(self, pattern_id: int) -> List[int]:
        n = len(self.files)
        
        match pattern_id:
            case 1:  # Sequential
                return list(range(n))
            case 2:  # Reverse Sequential
                return list(range(n-1, -1, -1))
            case 3:  # Random
                indices = list(range(n))
                random.shuffle(indices)
                return indices
            case 4:  # Zipfian
                return [random.choices(range(n), weights=[1/i for i in range(1, n+1)])[0] for _ in range(n)]
            case 5:  # Locality-Based
                group_size = 5
                indices = []
                for i in range(n):
                    group = (i // group_size) * group_size
                    offset = i % group_size
                    indices.append(min(group + offset, n - 1))
                return indices
            case 6:  # Repeated Access
                hot_size = max(n // 10, 1)
                hot_set = list(range(hot_size))
                return [random.choice(hot_set) if random.random() < 0.8 else random.randint(0, n-1) for _ in range(n)]
            case _:
                return list(range(n))
    
    def run_single(self, pattern_id: int) -> tuple[float, int]:
        access_order = self.get_access_pattern(pattern_id)
        
        start = time.time()
        total_bytes = 0
        
        for idx in access_order:
            with open(self.files[idx], 'rb') as f:
                data = f.read()
                total_bytes += len(data)
        
        return time.time() - start, total_bytes
    
    def run_pattern(self, pattern_id: int) -> Result:
        pattern_name = self.PATTERNS[pattern_id]
        durations = []
        bytes_read = []
        
        for _ in range(self.config.iterations):
            duration, bytes_count = self.run_single(pattern_id)
            durations.append(duration)
            bytes_read.append(bytes_count)
        
        avg_duration = sum(durations) / len(durations)
        avg_bytes = sum(bytes_read) / len(bytes_read)
        
        return Result(
            pattern=pattern_name,
            duration=avg_duration,
            file_count=len(self.files),
            bytes_read=avg_bytes,
            reads_per_sec=len(self.files) / avg_duration,
            mbytes_per_sec=avg_bytes / (1024 * 1024) / avg_duration
        )
    
    def run_all(self) -> Dict[str, Any]:
        self.create_files()
        results = []
        
        for pattern_id in self.config.patterns:
            print(f"Running {self.PATTERNS[pattern_id]}...")
            results.append(asdict(self.run_pattern(pattern_id)))
        
        self.cleanup()
        
        return {
            "config": asdict(self.config),
            "results": results,
            "system": {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "hostname": socket.gethostname()
            }
        }
    
    def cleanup(self):
        for file_path in self.files:
            os.remove(file_path)
        try:
            os.rmdir(self.config.target_dir)
        except OSError:
            pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-config", help="Configuration JSON file")
    parser.add_argument("-output", default="results.json", help="Output file")
    parser.add_argument("-files", type=int, default=100, help="Number of files")
    parser.add_argument("-size", type=int, default=1024, help="File size in KB")
    parser.add_argument("-dir", default="benchmark_files", help="Target directory")
    parser.add_argument("-iter", type=int, default=5, help="Iterations")
    
    args = parser.parse_args()
    
    if args.config:
        with open(args.config) as f:
            config_dict = json.load(f)
        config = Config(**config_dict)
    else:
        config = Config(
            num_files=args.files,
            file_size_kb=args.size,
            target_dir=args.dir,
            iterations=args.iter
        )
    
    benchmark = Benchmark(config)
    results = benchmark.run_all()
    
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {args.output}")
    print("\nSummary:")
    print(f"{'Pattern':<20} | {'Duration':<8} | {'MB/s':<7} | {'Files/s':<7}")
    print("-" * 50)
    
    for result in results["results"]:
        print(f"{result['pattern']:<20} | {result['duration']:>7.3f}s | {result['mbytes_per_sec']:>7.2f} | {result['reads_per_sec']:>7.2f}")

if __name__ == "__main__":
    main()
