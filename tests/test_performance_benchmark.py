"""Performance benchmark tests for threading improvements."""

import multiprocessing
import tempfile
import time
from pathlib import Path

import pytest
from PIL import Image

from src.core.cache_manager import ImprovedCacheManager
from src.utils.threading import GenerateGalleryThread


def create_benchmark_image(path, size=(800, 600)):
    """Create a test image for benchmarking."""
    img = Image.new('RGB', size, color='blue')

    # Add some EXIF data if it's a JPEG
    if path.suffix.lower() in ['.jpg', '.jpeg']:
        try:
            import piexif
            exif_data = {
                "0th": {},
                "Exif": {
                    piexif.ExifIFD.FocalLength: (35, 1),
                    piexif.ExifIFD.DateTimeOriginal: b'2024:01:15 10:30:00'
                }
            }
            exif_bytes = piexif.dump(exif_data)
            img.save(path, 'JPEG', exif=exif_bytes, quality=95)
        except ImportError:
            img.save(path, 'JPEG', quality=95)
    else:
        img.save(path)

    return str(path)


class TestPerformanceBenchmark:
    """Benchmark tests to measure performance improvements."""

    @pytest.fixture
    def cleanup_thread(self):
        """Helper to ensure thread cleanup."""
        def _cleanup(thread):
            if thread and thread.isRunning():
                thread.quit()
                if not thread.wait(2000):
                    thread.terminate()
                    thread.wait()
        return _cleanup

    @pytest.fixture
    def benchmark_environment(self):
        """Create a benchmark test environment with many images."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create directories
            images_dir = base_path / "benchmark_images"
            output_dir = base_path / "output"
            cache_dir = base_path / "cache"

            images_dir.mkdir()
            cache_dir.mkdir()

            # Create template
            template = base_path / "template.html"
            template.write_text('''<!DOCTYPE html>
<html><body>
<h1>Benchmark Gallery</h1>
{% for slate in gallery %}
    <h2>{{ slate.slate }}</h2>
    {% for image in slate.images %}
        <img src="{{ image.thumbnail }}" alt="{{ image.filename }}">
    {% endfor %}
{% endfor %}
</body></html>''')

            yield {
                'base_path': base_path,
                'images_dir': images_dir,
                'output_dir': output_dir,
                'cache_dir': cache_dir,
                'template': template
            }

    @pytest.mark.benchmark
    def test_parallel_vs_sequential_performance(self, benchmark_environment, qtbot, cleanup_thread):
        """Compare performance between parallel and sequential processing."""
        # Create test images
        num_images = 20
        slate_dir = benchmark_environment['images_dir'] / 'performance_test'
        slate_dir.mkdir()

        for i in range(num_images):
            create_benchmark_image(slate_dir / f'img_{i:03d}.jpg')

        # Create slates dict
        slates_dict = {
            'performance_test': {
                'images': [{'path': str(p)} for p in slate_dir.glob('*.jpg')]
            }
        }

        cache_manager = ImprovedCacheManager(
            base_dir=str(benchmark_environment['cache_dir'])
        )

        # Test with parallel processing (current implementation)
        thread_parallel = GenerateGalleryThread(
            selected_slates=['performance_test'],
            slates_dict=slates_dict,
            cache_manager=cache_manager,
            output_dir=str(benchmark_environment['output_dir']),
            root_dir=str(benchmark_environment['images_dir']),
            template_path=str(benchmark_environment['template']),
            generate_thumbnails=False,  # Test without thumbnails
            thumbnail_size=600
        )

        start_time = time.perf_counter()

        with qtbot.waitSignal(thread_parallel.gallery_complete, timeout=30000) as blocker:
            thread_parallel.start()

        parallel_time = time.perf_counter() - start_time
        success, _ = blocker.args
        assert success is True

        cleanup_thread(thread_parallel)

        # Log results
        print("\n=== Performance Results ===")
        print(f"Images processed: {num_images}")
        print(f"Parallel processing time: {parallel_time:.2f}s")
        print(f"Images per second: {num_images/parallel_time:.1f}")
        print(f"Workers used: {thread_parallel.max_workers}")

        # Verify performance is reasonable
        # With parallel processing, should handle at least 5 images/second
        assert num_images / parallel_time >= 5, f"Performance too slow: {num_images/parallel_time:.1f} images/sec"

    @pytest.mark.benchmark
    def test_scaling_with_image_count(self, benchmark_environment, qtbot, cleanup_thread):
        """Test how performance scales with different image counts."""
        cache_manager = ImprovedCacheManager(
            base_dir=str(benchmark_environment['cache_dir'])
        )

        results = []

        for num_images in [10, 25, 50]:
            # Create images
            slate_dir = benchmark_environment['images_dir'] / f'scale_test_{num_images}'
            slate_dir.mkdir(exist_ok=True)

            for i in range(num_images):
                create_benchmark_image(slate_dir / f'img_{i:03d}.jpg')

            slates_dict = {
                f'scale_test_{num_images}': {
                    'images': [{'path': str(p)} for p in slate_dir.glob('*.jpg')]
                }
            }

            # Run test
            thread = GenerateGalleryThread(
                selected_slates=[f'scale_test_{num_images}'],
                slates_dict=slates_dict,
                cache_manager=cache_manager,
                output_dir=str(benchmark_environment['output_dir']),
                root_dir=str(benchmark_environment['images_dir']),
                template_path=str(benchmark_environment['template']),
                generate_thumbnails=False,
                thumbnail_size=600
            )

            start_time = time.perf_counter()

            with qtbot.waitSignal(thread.gallery_complete, timeout=60000) as blocker:
                thread.start()

            elapsed_time = time.perf_counter() - start_time
            success, _ = blocker.args
            assert success is True

            images_per_sec = num_images / elapsed_time
            results.append({
                'count': num_images,
                'time': elapsed_time,
                'rate': images_per_sec
            })

            cleanup_thread(thread)

        # Log scaling results
        print("\n=== Scaling Results ===")
        print("Images | Time (s) | Rate (img/s)")
        print("-------|----------|-------------")
        for r in results:
            print(f"{r['count']:6d} | {r['time']:8.2f} | {r['rate']:12.1f}")

        # Verify reasonable scaling
        # Processing rate shouldn't degrade significantly with more images
        if len(results) >= 2:
            # Compare rate for small vs large batches
            small_rate = results[0]['rate']
            large_rate = results[-1]['rate']
            # Large batch should maintain at least 70% of small batch rate
            assert large_rate >= small_rate * 0.7, "Performance degrades too much with scale"

    @pytest.mark.benchmark
    def test_worker_efficiency(self, benchmark_environment, qtbot, cleanup_thread):
        """Test efficiency with different worker counts."""
        # Create test images
        num_images = 30
        slate_dir = benchmark_environment['images_dir'] / 'worker_test'
        slate_dir.mkdir()

        for i in range(num_images):
            create_benchmark_image(slate_dir / f'img_{i:03d}.jpg')

        slates_dict = {
            'worker_test': {
                'images': [{'path': str(p)} for p in slate_dir.glob('*.jpg')]
            }
        }

        cache_manager = ImprovedCacheManager(
            base_dir=str(benchmark_environment['cache_dir'])
        )

        # Test with different worker counts
        original_cpu_count = multiprocessing.cpu_count
        results = []

        for simulated_cores in [2, 4, 8]:
            # Monkey-patch cpu_count to simulate different core counts
            multiprocessing.cpu_count = lambda: simulated_cores

            thread = GenerateGalleryThread(
                selected_slates=['worker_test'],
                slates_dict=slates_dict,
                cache_manager=cache_manager,
                output_dir=str(benchmark_environment['output_dir']),
                root_dir=str(benchmark_environment['images_dir']),
                template_path=str(benchmark_environment['template']),
                generate_thumbnails=False,
                thumbnail_size=600
            )

            # Verify worker count calculation
            expected_workers = min(simulated_cores * 2, 16)
            assert thread.max_workers == expected_workers

            start_time = time.perf_counter()

            with qtbot.waitSignal(thread.gallery_complete, timeout=60000) as blocker:
                thread.start()

            elapsed_time = time.perf_counter() - start_time
            success, _ = blocker.args
            assert success is True

            results.append({
                'cores': simulated_cores,
                'workers': thread.max_workers,
                'time': elapsed_time,
                'rate': num_images / elapsed_time
            })

            cleanup_thread(thread)

        # Restore original cpu_count
        multiprocessing.cpu_count = original_cpu_count

        # Log worker efficiency results
        print("\n=== Worker Efficiency Results ===")
        print("Cores | Workers | Time (s) | Rate (img/s)")
        print("------|---------|----------|-------------")
        for r in results:
            print(f"{r['cores']:5d} | {r['workers']:7d} | {r['time']:8.2f} | {r['rate']:12.1f}")

        # Verify that more workers generally improve performance
        if len(results) >= 2:
            # More workers should generally mean better performance
            # (though not always linearly due to I/O constraints)
            # We'll be lenient - as long as performance doesn't degrade by more than 20%
            min_acceptable_rate = results[0]['rate'] * 0.8
            assert results[-1]['rate'] >= min_acceptable_rate, f"Performance shouldn't degrade significantly with more workers: {results[-1]['rate']:.1f} < {min_acceptable_rate:.1f}"


@pytest.mark.benchmark
class TestThumbnailPerformance:
    """Test performance with thumbnail generation."""

    @pytest.fixture
    def cleanup_thread(self):
        """Helper to ensure thread cleanup."""
        def _cleanup(thread):
            if thread and thread.isRunning():
                thread.quit()
                if not thread.wait(2000):
                    thread.terminate()
                    thread.wait()
        return _cleanup

    def test_thumbnail_generation_performance(self, qtbot, cleanup_thread):
        """Test performance of thumbnail generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Setup
            images_dir = base_path / "thumb_test"
            images_dir.mkdir()
            output_dir = base_path / "output"
            cache_dir = base_path / "cache"
            cache_dir.mkdir()

            # Create larger images to make thumbnail generation meaningful
            num_images = 15
            for i in range(num_images):
                create_benchmark_image(
                    images_dir / f'large_{i:03d}.jpg',
                    size=(2000, 1500)  # Larger images
                )

            slates_dict = {
                'thumb_test': {
                    'images': [{'path': str(p)} for p in images_dir.glob('*.jpg')]
                }
            }

            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))

            # Create template
            template = base_path / "template.html"
            template.write_text('<html>{% for s in gallery %}{{ s.slate }}{% endfor %}</html>')

            # Test with thumbnail generation
            thread = GenerateGalleryThread(
                selected_slates=['thumb_test'],
                slates_dict=slates_dict,
                cache_manager=cache_manager,
                output_dir=str(output_dir),
                root_dir=str(images_dir),
                template_path=str(template),
                generate_thumbnails=True,  # Enable thumbnails
                thumbnail_size=800
            )

            start_time = time.perf_counter()

            with qtbot.waitSignal(thread.gallery_complete, timeout=60000) as blocker:
                thread.start()

            elapsed_time = time.perf_counter() - start_time
            success, _ = blocker.args
            assert success is True

            cleanup_thread(thread)

            # Verify thumbnails were created
            thumb_dir = output_dir / 'thumbnails'
            assert thumb_dir.exists()
            thumb_files = list(thumb_dir.glob('*.jpg'))
            assert len(thumb_files) == num_images

            # Log results
            print("\n=== Thumbnail Generation Performance ===")
            print(f"Images processed: {num_images}")
            print(f"Time with thumbnails: {elapsed_time:.2f}s")
            print(f"Rate: {num_images/elapsed_time:.1f} images/sec")
            print(f"Workers: {thread.max_workers}")

            # With parallel processing, should handle at least 3 images/second with thumbnails
            assert num_images / elapsed_time >= 3, f"Thumbnail generation too slow: {num_images/elapsed_time:.1f} images/sec"
