package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"math/rand"
	"os"
	"path/filepath"
	"time"
)

type BenchmarkConfig struct {
	NumFiles        int    `json:"numFiles"`
	FileSizeKB      int    `json:"fileSizeKB"`
	ReadPatterns    []int  `json:"readPatterns"`
	TargetDirectory string `json:"targetDirectory"`
	Iterations      int    `json:"iterations"`
}

type BenchmarkResult struct {
	Pattern      string        `json:"pattern"`
	Duration     time.Duration `json:"duration"`
	FileCount    int           `json:"fileCount"`
	BytesRead    int64         `json:"bytesRead"`
	ReadPerSec   float64       `json:"reads_per_sec"`
	MBytesPerSec float64       `json:"mbytes_per_sec"`
}

type BenchmarkResults struct {
	Config  BenchmarkConfig   `json:"config"`
	Results []BenchmarkResult `json:"results"`
	System  struct {
		Timestamp string `json:"timestamp"`
		Hostname  string `json:"hostname"`
	} `json:"system"`
}

type FileInfo struct {
	Path     string
	Size     int64
	Contents []byte
}

const (
	PatternSequential     = 1
	PatternReverseSeq     = 2
	PatternRandom         = 3
	PatternZipfian        = 4
	PatternLocalityBased  = 5
	PatternRepeatedAccess = 6
)

func main() {
	configPath := flag.String("config", "", "Path to configuration JSON file")
	outputPath := flag.String("output", "benchmark_results.json", "Path to output JSON results")
	numFiles := flag.Int("files", 100, "Number of files to create")
	fileSizeKB := flag.Int("size", 1024, "Size of each file in KB")
	targetDir := flag.String("dir", "benchmark_files", "Directory to create files in")
	iterations := flag.Int("iter", 10, "Number of iterations for each benchmark")
	flag.Parse()

	var config BenchmarkConfig

	if *configPath != "" {
		data, err := os.ReadFile(*configPath)
		if err != nil {
			fmt.Printf("Error reading config file: %v\n", err)
			os.Exit(1)
		}
		if err := json.Unmarshal(data, &config); err != nil {
			fmt.Printf("Error parsing config file: %v\n", err)
			os.Exit(1)
		}
	} else {
		config = BenchmarkConfig{
			NumFiles:        *numFiles,
			FileSizeKB:      *fileSizeKB,
			ReadPatterns:    []int{PatternSequential, PatternReverseSeq, PatternRandom, PatternZipfian, PatternLocalityBased, PatternRepeatedAccess},
			TargetDirectory: *targetDir,
			Iterations:      *iterations,
		}
	}

	results := BenchmarkResults{
		Config:  config,
		Results: []BenchmarkResult{},
	}

	hostname, _ := os.Hostname()
	results.System.Hostname = hostname
	results.System.Timestamp = time.Now().Format(time.RFC3339)

	err := os.MkdirAll(config.TargetDirectory, 0755)
	if err != nil {
		fmt.Printf("Error creating target directory: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("Creating %d files of %d KB each in %s...\n", config.NumFiles, config.FileSizeKB, config.TargetDirectory)
	files, err := createTestFiles(config.TargetDirectory, config.NumFiles, config.FileSizeKB*1024)
	if err != nil {
		fmt.Printf("Error creating test files: %v\n", err)
		os.Exit(1)
	}

	for _, patternID := range config.ReadPatterns {
		patternName := getPatternName(patternID)
		fmt.Printf("Running benchmark for %s pattern (%d iterations)...\n", patternName, config.Iterations)

		var totalDuration time.Duration
		var totalBytes int64

		for i := 0; i < config.Iterations; i++ {
			fmt.Printf("  Iteration %d/%d...\n", i+1, config.Iterations)
			duration, bytesRead, err := runBenchmark(files, patternID)
			if err != nil {
				fmt.Printf("Error running benchmark: %v\n", err)
				continue
			}
			totalDuration += duration
			totalBytes += bytesRead
		}

		avgDuration := totalDuration / time.Duration(config.Iterations)
		avgBytes := totalBytes / int64(config.Iterations)

		fileCount := len(files)
		readPerSec := float64(fileCount) / avgDuration.Seconds()
		mbytesPerSec := float64(avgBytes) / 1024 / 1024 / avgDuration.Seconds()

		results.Results = append(results.Results, BenchmarkResult{
			Pattern:      patternName,
			Duration:     avgDuration,
			FileCount:    fileCount,
			BytesRead:    avgBytes,
			ReadPerSec:   readPerSec,
			MBytesPerSec: mbytesPerSec,
		})

		fmt.Printf("  Result: %.2f MB/s, %.2f files/s\n", mbytesPerSec, readPerSec)
	}

	fmt.Println("Cleaning up...")
	cleanupFiles(files)

	resultData, err := json.MarshalIndent(results, "", "  ")
	if err != nil {
		fmt.Printf("Error serializing results: %v\n", err)
		os.Exit(1)
	}

	err = os.WriteFile(*outputPath, resultData, 0644)
	if err != nil {
		fmt.Printf("Error writing results to %s: %v\n", *outputPath, err)
		os.Exit(1)
	}

	fmt.Printf("Benchmark complete. Results saved to %s\n", *outputPath)

	fmt.Println("\nSummary:")
	fmt.Println("Pattern               | Duration  | MB/s    | Files/s")
	fmt.Println("----------------------|-----------|---------|---------")
	for _, result := range results.Results {
		fmt.Printf("%-20s | %9.3fs | %7.2f | %7.2f\n",
			result.Pattern,
			result.Duration.Seconds(),
			result.MBytesPerSec,
			result.ReadPerSec)
	}
}

func createTestFiles(dir string, count, sizeBytes int) ([]FileInfo, error) {
	files := make([]FileInfo, count)

	for i := 0; i < count; i++ {
		filename := filepath.Join(dir, fmt.Sprintf("test_file_%04d.dat", i))

		data := make([]byte, sizeBytes)
		rand.Read(data)

		err := os.WriteFile(filename, data, 0644)
		if err != nil {
			return nil, fmt.Errorf("failed to write file %s: %w", filename, err)
		}

		files[i] = FileInfo{
			Path:     filename,
			Size:     int64(sizeBytes),
			Contents: data,
		}
	}

	return files, nil
}

func runBenchmark(files []FileInfo, patternID int) (time.Duration, int64, error) {
	accessOrder := createAccessPattern(files, patternID)

	startTime := time.Now()
	totalBytes := int64(0)

	for _, idx := range accessOrder {
		file := files[idx]
		data, err := os.ReadFile(file.Path)
		if err != nil {
			return 0, 0, fmt.Errorf("failed to read file %s: %w", file.Path, err)
		}
		totalBytes += int64(len(data))
	}

	duration := time.Since(startTime)
	return duration, totalBytes, nil
}

func createAccessPattern(files []FileInfo, patternID int) []int {
	n := len(files)
	indices := make([]int, n)

	switch patternID {
	case PatternSequential:
		for i := 0; i < n; i++ {
			indices[i] = i
		}

	case PatternReverseSeq:
		for i := 0; i < n; i++ {
			indices[i] = n - 1 - i
		}

	case PatternRandom:
		for i := 0; i < n; i++ {
			indices[i] = i
		}
		rand.Shuffle(n, func(i, j int) {
			indices[i], indices[j] = indices[j], indices[i]
		})

	case PatternZipfian:
		// Zipfian distribution - some files accessed much more frequently
		zipf := rand.NewZipf(rand.New(rand.NewSource(time.Now().UnixNano())), 1.1, 1.0, uint64(n-1))
		for i := 0; i < n; i++ {
			indices[i] = int(zipf.Uint64())
		}

	case PatternLocalityBased:
		// Access files in small groups, then jump
		groupSize := 5
		for i := 0; i < n; i++ {
			group := (i / groupSize) * groupSize
			offset := i % groupSize
			indices[i] = group + offset
			if indices[i] >= n {
				indices[i] = n - 1
			}
		}

	case PatternRepeatedAccess:
		// 80% of accesses to a hot set (top 10% of files)
		hotSetSize := n / 10
		if hotSetSize < 1 {
			hotSetSize = 1
		}

		hotSet := make([]int, hotSetSize)
		for i := 0; i < hotSetSize; i++ {
			hotSet[i] = i
		}

		for i := 0; i < n; i++ {
			if rand.Float32() < 0.8 {
				indices[i] = hotSet[rand.Intn(hotSetSize)]
			} else {
				indices[i] = rand.Intn(n)
			}
		}

	default:
		for i := 0; i < n; i++ {
			indices[i] = i
		}
	}

	return indices
}

func cleanupFiles(files []FileInfo) {
	for _, file := range files {
		os.Remove(file.Path)
	}

	if len(files) > 0 {
		dir := filepath.Dir(files[0].Path)
		os.Remove(dir)
	}
}

func getPatternName(patternID int) string {
	switch patternID {
	case PatternSequential:
		return "Sequential"
	case PatternReverseSeq:
		return "Reverse Sequential"
	case PatternRandom:
		return "Random"
	case PatternZipfian:
		return "Zipfian"
	case PatternLocalityBased:
		return "Locality-Based"
	case PatternRepeatedAccess:
		return "Repeated Access"
	default:
		return fmt.Sprintf("Unknown Pattern %d", patternID)
	}
}
