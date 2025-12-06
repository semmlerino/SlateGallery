"""Improved threading tests using real components instead of excessive mocks."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from src.core.cache_manager import ImprovedCacheManager
from src.utils.threading import GenerateGalleryThread, ScanThread


def create_real_test_image(path, size=(100, 100), focal_length=None, date_taken=None):
    """Create a real test image file with optional EXIF data."""
    img = Image.new('RGB', size, color='red')

    if (focal_length or date_taken) and path.suffix.lower() == '.jpg':
        try:
            import piexif
            exif_data = {"0th": {}, "Exif": {}}

            if focal_length:
                exif_data["Exif"][piexif.ExifIFD.FocalLength] = (int(focal_length), 1)

            if date_taken:
                date_str = date_taken.strftime('%Y:%m:%d %H:%M:%S')
                exif_data["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str.encode('utf-8')

            exif_bytes = piexif.dump(exif_data)
            img.save(path, 'JPEG', exif=exif_bytes)
        except ImportError:
            img.save(path, 'JPEG')
    else:
        format = 'PNG' if path.suffix.lower() == '.png' else 'JPEG'
        img.save(path, format)

    return str(path)


class TestScanThreadImproved:
    """Test ScanThread with real cache manager and images."""

    @pytest.fixture
    def real_test_environment(self):
        """Create a real test environment with images and cache."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create image directories
            images_dir = base_path / "images"
            cache_dir = base_path / "cache"

            images_dir.mkdir()
            cache_dir.mkdir()

            # Create real subdirectories with images
            vacation_dir = images_dir / "vacation_2024"
            vacation_dir.mkdir()
            create_real_test_image(vacation_dir / "beach1.jpg", focal_length=24)
            create_real_test_image(vacation_dir / "beach2.jpg", focal_length=35)
            create_real_test_image(vacation_dir / "sunset.png")

            family_dir = images_dir / "family_photos"
            family_dir.mkdir()
            create_real_test_image(family_dir / "portrait1.jpg", size=(150, 200), focal_length=85)
            create_real_test_image(family_dir / "portrait2.jpg", size=(150, 200), focal_length=85)

            # Create real cache manager
            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))

            yield {
                'base_path': base_path,
                'images_dir': str(images_dir),
                'cache_dir': str(cache_dir),
                'cache_manager': cache_manager
            }

    def test_scan_thread_with_real_components(self, real_test_environment, qtbot, thread_cleanup):
        """Test ScanThread with real cache manager and real images."""
        thread = thread_cleanup(ScanThread(
            real_test_environment['images_dir'],
            real_test_environment['cache_manager']
        ))

        # Capture signals
        with qtbot.waitSignal(thread.scan_complete, timeout=5000) as blocker:
            thread.start()

        # Get results
        slates_result, message = blocker.args

        # Verify real scanning occurred
        assert isinstance(slates_result, dict)
        assert 'vacation_2024' in slates_result
        assert 'family_photos' in slates_result

        # Verify correct number of images found
        assert len(slates_result['vacation_2024']['images']) == 3
        assert len(slates_result['family_photos']['images']) == 2

        # Verify cache was actually saved
        cache_file = Path(real_test_environment['cache_dir']) / real_test_environment['cache_manager'].get_cache_file(
            real_test_environment['images_dir']
        )
        assert cache_file.exists()

        # Verify completion message
        assert "complete" in message.lower()

    def test_scan_thread_progress_reporting(self, real_test_environment, qtbot, thread_cleanup):
        """Test that scan thread reports progress correctly."""
        thread = thread_cleanup(ScanThread(
            real_test_environment['images_dir'],
            real_test_environment['cache_manager']
        ))

        progress_values = []
        thread.progress.connect(lambda value: progress_values.append(value))

        with qtbot.waitSignal(thread.scan_complete, timeout=5000):
            thread.start()

        # Should have received progress values (integers representing percentage)
        assert len(progress_values) > 0
        assert all(isinstance(v, int) for v in progress_values)
        assert any(v == 100 for v in progress_values)  # Should reach 100%

    def test_scan_thread_cache_persistence(self, real_test_environment, qtbot, thread_cleanup):
        """Test that scan results are properly cached and retrievable."""
        # First scan
        thread1 = thread_cleanup(ScanThread(
            real_test_environment['images_dir'],
            real_test_environment['cache_manager']
        ))

        with qtbot.waitSignal(thread1.scan_complete, timeout=5000) as blocker:
            thread1.start()

        first_result, _ = blocker.args

        # Load from cache
        cached_data = real_test_environment['cache_manager'].load_cache(
            real_test_environment['images_dir']
        )

        # Verify cache matches scan result
        assert cached_data == first_result

        # Second scan should use cache
        thread2 = thread_cleanup(ScanThread(
            real_test_environment['images_dir'],
            real_test_environment['cache_manager']
        ))

        with qtbot.waitSignal(thread2.scan_complete, timeout=5000) as blocker:
            thread2.start()

        second_result, _ = blocker.args

        # Results should be identical
        assert second_result == first_result


class TestGenerateGalleryThreadImproved:
    """Test GenerateGalleryThread with real components."""

    @pytest.fixture
    def gallery_test_environment(self):
        """Create a complete gallery test environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create directories
            images_dir = base_path / "images"
            output_dir = base_path / "output"
            cache_dir = base_path / "cache"
            templates_dir = base_path / "templates"

            for dir in [images_dir, cache_dir, templates_dir]:
                dir.mkdir()

            # Create template
            template_file = templates_dir / "gallery.html"
            template_file.write_text('''<!DOCTYPE html>
<html><body>
<h1>Gallery</h1>
{% for focal in focal_lengths %}
    <div>{{ focal.value }}mm: {{ focal.count }} photos</div>
{% endfor %}
{% for date in dates %}
    <div>{{ date.value }}: {{ date.count }} photos</div>
{% endfor %}
{% for slate in gallery %}
    <h2>{{ slate.slate }}</h2>
    {% for image in slate.images %}
        <img src="{{ image.web_path }}" alt="{{ image.filename }}">
    {% endfor %}
{% endfor %}
</body></html>''')

            # Create test images with metadata
            vacation_dir = images_dir / "vacation"
            vacation_dir.mkdir()

            create_real_test_image(
                vacation_dir / "beach.jpg",
                focal_length=24,
                date_taken=datetime(2024, 7, 15, 10, 30)
            )
            create_real_test_image(
                vacation_dir / "sunset.jpg",
                focal_length=35,
                date_taken=datetime(2024, 7, 15, 18, 45)
            )
            create_real_test_image(
                vacation_dir / "hotel.jpg",
                focal_length=24,
                date_taken=datetime(2024, 7, 16, 9, 0)
            )

            # Create cache manager
            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))

            # Create slates dict
            slates_dict = {
                'vacation': {
                    'images': [
                        {'path': str(vacation_dir / "beach.jpg")},
                        {'path': str(vacation_dir / "sunset.jpg")},
                        {'path': str(vacation_dir / "hotel.jpg")}
                    ]
                }
            }

            yield {
                'base_path': base_path,
                'images_dir': str(images_dir),
                'output_dir': str(output_dir),
                'cache_manager': cache_manager,
                'template_path': str(template_file),
                'slates_dict': slates_dict
            }

    def test_generate_gallery_thread_with_real_components(self, gallery_test_environment, qtbot, thread_cleanup):
        """Test gallery generation with real cache and images."""
        thread = thread_cleanup(GenerateGalleryThread(
            selected_slates=['vacation'],
            slates_dict=gallery_test_environment['slates_dict'],
            cache_manager=gallery_test_environment['cache_manager'],
            output_dir=gallery_test_environment['output_dir'],
            allowed_root_dirs=gallery_test_environment['images_dir'],
            template_path=gallery_test_environment['template_path'],
            generate_thumbnails=False,
            thumbnail_size=600
        ))

        with qtbot.waitSignal(thread.gallery_complete, timeout=10000) as blocker:
            thread.start()

        success, message = blocker.args

        # Verify success
        assert success is True
        assert "generated" in message.lower()

        # Verify output file exists
        output_file = Path(gallery_test_environment['output_dir']) / 'index.html'
        assert output_file.exists()

        # Verify content
        content = output_file.read_text()
        assert 'vacation' in content
        assert 'beach.jpg' in content
        assert 'sunset.jpg' in content
        assert 'hotel.jpg' in content

        # Verify focal length data collected
        assert thread.focal_length_counts.get(24.0, 0) == 2
        assert thread.focal_length_counts.get(35.0, 0) == 1

        # Verify date data collected (with day-level granularity)
        assert thread.date_counts.get('2024-07-15', 0) == 2
        assert thread.date_counts.get('2024-07-16', 0) == 1

        # Thread cleanup handled by fixture

    def test_generate_gallery_with_thumbnails(self, gallery_test_environment, qtbot, thread_cleanup):
        """Test gallery generation with thumbnail creation."""
        thread = thread_cleanup(GenerateGalleryThread(
            selected_slates=['vacation'],
            slates_dict=gallery_test_environment['slates_dict'],
            cache_manager=gallery_test_environment['cache_manager'],
            output_dir=gallery_test_environment['output_dir'],
            allowed_root_dirs=gallery_test_environment['images_dir'],
            template_path=gallery_test_environment['template_path'],
            generate_thumbnails=True,  # Enable thumbnails
            thumbnail_size=800
        ))

        with qtbot.waitSignal(thread.gallery_complete, timeout=15000) as blocker:
            thread.start()

        success, _message = blocker.args

        assert success is True

        # Verify thumbnails were created
        thumb_dir = Path(gallery_test_environment['output_dir']) / 'thumbnails'
        assert thumb_dir.exists()

        # Should have thumbnails for each image
        thumb_files = list(thumb_dir.glob("*.jpg"))
        assert len(thumb_files) > 0

        # Thread cleanup handled by fixture

    def test_gallery_thread_error_recovery(self, gallery_test_environment, qtbot, thread_cleanup):
        """Test that gallery thread handles missing template gracefully."""
        # Use non-existent template to trigger error
        thread = thread_cleanup(GenerateGalleryThread(
            selected_slates=['vacation'],
            slates_dict=gallery_test_environment['slates_dict'],
            cache_manager=gallery_test_environment['cache_manager'],
            output_dir=gallery_test_environment['output_dir'],
            allowed_root_dirs=gallery_test_environment['images_dir'],
            template_path='/nonexistent/template.html',
            generate_thumbnails=False,
            thumbnail_size=600
        ))

        with qtbot.waitSignal(thread.gallery_complete, timeout=5000) as blocker:
            thread.start()

        success, message = blocker.args

        # Missing template should fail gracefully
        assert success is False, "Missing template should result in failure"
        assert "error" in message.lower() or "failed" in message.lower(), (
            f"Error message should indicate failure, got: {message}"
        )

    def test_parallel_processing_without_thumbnails(self, gallery_test_environment, qtbot, thread_cleanup):
        """Test that parallel processing is used even without thumbnails."""
        # Create more images to test parallel processing
        vacation_dir = Path(gallery_test_environment['images_dir']) / 'vacation'
        for i in range(10):
            create_real_test_image(
                vacation_dir / f'extra_{i}.jpg',
                focal_length=50,
                date_taken=datetime(2024, 7, 17, 10, i)
            )

        # Update slates dict with new images
        gallery_test_environment['slates_dict']['vacation']['images'] = [
            {'path': str(vacation_dir / f)}
            for f in vacation_dir.glob('*.jpg')
        ]

        thread = thread_cleanup(GenerateGalleryThread(
            selected_slates=['vacation'],
            slates_dict=gallery_test_environment['slates_dict'],
            cache_manager=gallery_test_environment['cache_manager'],
            output_dir=gallery_test_environment['output_dir'],
            allowed_root_dirs=gallery_test_environment['images_dir'],
            template_path=gallery_test_environment['template_path'],
            generate_thumbnails=False,  # Thumbnails disabled
            thumbnail_size=600
        ))

        # Verify correct worker count
        import multiprocessing
        expected_workers = min(multiprocessing.cpu_count() * 2, 16)
        assert thread.max_workers == expected_workers

        with qtbot.waitSignal(thread.gallery_complete, timeout=10000) as blocker:
            thread.start()

        success, _message = blocker.args
        assert success is True

        # Thread should have processed multiple images in parallel
        # Check that all images were processed
        output_file = Path(gallery_test_environment['output_dir']) / 'index.html'
        content = output_file.read_text()
        assert 'extra_0.jpg' in content
        assert 'extra_9.jpg' in content

    def test_worker_count_calculation(self, gallery_test_environment, qtbot, thread_cleanup):
        """Test that worker count is calculated correctly."""
        import multiprocessing

        thread = thread_cleanup(GenerateGalleryThread(
            selected_slates=['vacation'],
            slates_dict=gallery_test_environment['slates_dict'],
            cache_manager=gallery_test_environment['cache_manager'],
            output_dir=gallery_test_environment['output_dir'],
            allowed_root_dirs=gallery_test_environment['images_dir'],
            template_path=gallery_test_environment['template_path'],
            generate_thumbnails=False,
            thumbnail_size=600
        ))

        # Worker count should be 2x CPU count, max 16
        expected = min(multiprocessing.cpu_count() * 2, 16)
        assert thread.max_workers == expected

        # Should be at least 2 workers
        assert thread.max_workers >= 2

        # Should not exceed 16
        assert thread.max_workers <= 16

    def test_performance_logging(self, gallery_test_environment, qtbot, thread_cleanup, caplog):
        """Test that performance metrics are logged."""
        import logging
        caplog.set_level(logging.INFO)

        # Create multiple images for meaningful performance test
        vacation_dir = Path(gallery_test_environment['images_dir']) / 'vacation'
        for i in range(5):
            create_real_test_image(vacation_dir / f'perf_{i}.jpg')

        gallery_test_environment['slates_dict']['vacation']['images'] = [
            {'path': str(vacation_dir / f)}
            for f in vacation_dir.glob('*.jpg')
        ]

        thread = thread_cleanup(GenerateGalleryThread(
            selected_slates=['vacation'],
            slates_dict=gallery_test_environment['slates_dict'],
            cache_manager=gallery_test_environment['cache_manager'],
            output_dir=gallery_test_environment['output_dir'],
            allowed_root_dirs=gallery_test_environment['images_dir'],
            template_path=gallery_test_environment['template_path'],
            generate_thumbnails=False,
            thumbnail_size=600
        ))

        with qtbot.waitSignal(thread.gallery_complete, timeout=10000):
            thread.start()

        # Check for performance logging
        performance_logged = False
        for record in caplog.records:
            if "images/sec" in record.message and "workers" in record.message:
                performance_logged = True
                # Verify the log contains expected information
                assert "Processed" in record.message
                assert "images in" in record.message
                assert "using" in record.message
                break

        assert performance_logged, "Performance metrics should be logged"


class TestThreadingIntegrationImproved:
    """Integration tests with real components."""

    def test_full_scan_and_generate_workflow(self, qtbot, thread_cleanup):
        """Test complete workflow with real components."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Set up environment
            images_dir = base_path / "photos"
            output_dir = base_path / "gallery"
            cache_dir = base_path / "cache"

            images_dir.mkdir()
            cache_dir.mkdir()

            # Create images
            for i in range(3):
                img_path = images_dir / f"img_{i}.jpg"
                create_real_test_image(img_path, focal_length=35 + i*10)

            # Create template
            template = base_path / "template.html"
            template.write_text('<html>{% for s in gallery %}{{ s.slate }}{% endfor %}</html>')

            # Create cache manager
            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))

            # Step 1: Scan
            scan_thread = thread_cleanup(ScanThread(str(images_dir), cache_manager))

            with qtbot.waitSignal(scan_thread.scan_complete, timeout=5000) as blocker:
                scan_thread.start()

            slates_dict, _ = blocker.args

            # Step 2: Generate gallery
            selected_slates = list(slates_dict.keys())

            gen_thread = thread_cleanup(GenerateGalleryThread(
                selected_slates=selected_slates,
                slates_dict=slates_dict,
                cache_manager=cache_manager,
                output_dir=str(output_dir),
                allowed_root_dirs=str(images_dir),
                template_path=str(template),
                generate_thumbnails=False,
                thumbnail_size=600
            ))

            with qtbot.waitSignal(gen_thread.gallery_complete, timeout=10000) as blocker:
                gen_thread.start()

            success, _ = blocker.args

            assert success is True
            assert (output_dir / 'index.html').exists()

            # Thread cleanup handled by fixture


class TestThreadSafety:
    """Test thread safety improvements."""

    def test_signal_stop_method(self, qtbot, thread_cleanup):
        """Test that signal_stop() sets stop event without waiting."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            images_dir = base_path / "images"
            cache_dir = base_path / "cache"
            images_dir.mkdir()
            cache_dir.mkdir()

            # Create a lot of images to ensure thread takes a while
            for i in range(20):
                create_real_test_image(images_dir / f"img_{i}.jpg")

            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))
            thread = thread_cleanup(ScanThread(str(images_dir), cache_manager))

            thread.start()

            # Wait a tiny bit for thread to start
            import time
            time.sleep(0.1)

            # signal_stop() should return immediately (not wait for thread)
            start = time.time()
            thread.signal_stop()
            duration = time.time() - start

            # signal_stop should be nearly instant (< 0.1 seconds)
            assert duration < 0.5, f"signal_stop() took {duration}s, should be instant"

            # Now wait for thread to actually stop
            thread.wait(5000)

    def test_stop_during_exif_processing(self, qtbot, thread_cleanup):
        """Test that stop event cancels EXIF processing.

        This test verifies that when stop_event is set before processing,
        the method returns early with no results.
        """
        import threading

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            images_dir = base_path / "images"
            cache_dir = base_path / "cache"
            images_dir.mkdir()
            cache_dir.mkdir()

            # Create images
            for i in range(10):
                create_real_test_image(images_dir / f"img_{i}.jpg", focal_length=35)

            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))

            # Create stop event and SET IT BEFORE PROCESSING
            stop_event = threading.Event()
            stop_event.set()  # Already signaled

            # Get image paths
            image_paths = [str(p) for p in images_dir.glob("*.jpg")]

            # Process with pre-set stop event - should return immediately with no results
            result = cache_manager.process_images_batch_with_exif(
                image_paths,
                None,
                None,
                stop_event,
            )

            # Processing should have been stopped immediately (no results)
            assert len(result) == 0, (
                f"Got {len(result)} results but expected 0 when stop_event is pre-set"
            )

    def test_concurrent_cache_file_access(self, qtbot):
        """Test that cache file I/O is protected by lock."""
        import threading

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_manager = ImprovedCacheManager(base_dir=temp_dir)

            # Create test data
            test_slates = {"test_slate": {"images": [{"path": "/test/img.jpg"}]}}
            root_dir = str(Path(temp_dir) / "test_dir")
            Path(root_dir).mkdir()

            # Track any errors
            errors: list[Exception] = []
            operations_count = 0
            operations_lock = threading.Lock()

            def save_worker():
                nonlocal operations_count
                try:
                    for _ in range(10):
                        cache_manager.save_cache(root_dir, test_slates)
                        with operations_lock:
                            operations_count += 1
                except Exception as e:
                    errors.append(e)

            def load_worker():
                nonlocal operations_count
                try:
                    for _ in range(10):
                        cache_manager.load_cache(root_dir)
                        with operations_lock:
                            operations_count += 1
                except Exception as e:
                    errors.append(e)

            def validate_worker():
                nonlocal operations_count
                try:
                    for _ in range(10):
                        cache_manager.validate_cache(root_dir)
                        with operations_lock:
                            operations_count += 1
                except Exception as e:
                    errors.append(e)

            # Start multiple threads accessing cache concurrently
            threads = [
                threading.Thread(target=save_worker),
                threading.Thread(target=load_worker),
                threading.Thread(target=validate_worker),
                threading.Thread(target=save_worker),
                threading.Thread(target=load_worker),
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join(timeout=10)

            # No errors should have occurred (lock protects file access)
            assert len(errors) == 0, f"Concurrent access errors: {errors}"
            assert operations_count == 50, f"Expected 50 operations, got {operations_count}"

    def test_parallel_thread_shutdown(self, qtbot, thread_cleanup):
        """Test that multiple threads can be stopped in parallel."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create two image directories
            dir1 = base_path / "dir1"
            dir2 = base_path / "dir2"
            dir1.mkdir()
            dir2.mkdir()
            cache_dir = base_path / "cache"
            cache_dir.mkdir()

            # Create images in both
            for i in range(10):
                create_real_test_image(dir1 / f"img_{i}.jpg")
                create_real_test_image(dir2 / f"img_{i}.jpg")

            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))

            # Create two threads
            thread1 = thread_cleanup(ScanThread(str(dir1), cache_manager))
            thread2 = thread_cleanup(ScanThread(str(dir2), cache_manager))

            thread1.start()
            thread2.start()

            # Wait for threads to start
            import time
            time.sleep(0.1)

            # Signal both to stop (parallel)
            start = time.time()
            thread1.signal_stop()
            thread2.signal_stop()
            signal_duration = time.time() - start

            # Signaling should be fast
            assert signal_duration < 0.1, f"Signaling took {signal_duration}s, should be instant"

            # Wait for both (they're now stopping in parallel)
            thread1.wait(5000)
            thread2.wait(5000)

            # Both threads should be stopped
            assert not thread1.isRunning()
            assert not thread2.isRunning()


class TestParallelSlateProcessing:
    """Tests for parallel EXIF processing (3+ slates).

    The parallel code path triggers when scanning 3+ slates,
    using ThreadPoolExecutor for slate-level parallelism.
    """

    @pytest.fixture
    def multi_slate_environment(self):
        """Create environment with 4+ slate directories for parallel processing tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)

            # Create image directories (4 slates to trigger parallel path)
            images_dir = base_path / "images"
            cache_dir = base_path / "cache"

            images_dir.mkdir()
            cache_dir.mkdir()

            # Create 4 slate directories with different image counts
            slate_dirs = []
            for i in range(4):
                slate_name = f"slate_{i}"
                slate_dir = images_dir / slate_name
                slate_dir.mkdir()
                slate_dirs.append(slate_dir)

                # Create 3 images per slate with varied EXIF data
                for j in range(3):
                    focal = 24 + (i * 10) + (j * 5)  # 24-69mm range
                    create_real_test_image(
                        slate_dir / f"img_{j}.jpg",
                        focal_length=focal,
                        date_taken=datetime(2024, 7, 15 + i, 10 + j)
                    )

            # Create cache manager
            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))

            yield {
                'base_path': base_path,
                'images_dir': str(images_dir),
                'cache_dir': str(cache_dir),
                'cache_manager': cache_manager,
                'slate_dirs': slate_dirs,
                'total_images': 12  # 4 slates * 3 images
            }

    def test_parallel_path_triggered_with_4_slates(self, multi_slate_environment, qtbot, thread_cleanup, caplog):
        """Verify parallel code path activates with 4+ slates."""
        import logging
        caplog.set_level(logging.INFO)

        thread = thread_cleanup(ScanThread(
            multi_slate_environment['images_dir'],
            multi_slate_environment['cache_manager']
        ))

        with qtbot.waitSignal(thread.scan_complete, timeout=10000) as blocker:
            thread.start()

        slates_result, _message = blocker.args

        # Verify we got all 4 slates
        assert len(slates_result) == 4

        # Verify parallel processing was triggered (check log messages)
        parallel_triggered = any(
            "slates in parallel" in record.message
            for record in caplog.records
        )
        assert parallel_triggered, "Expected parallel processing to be triggered for 4 slates"

    def test_parallel_processing_completes_all_slates(self, multi_slate_environment, qtbot, thread_cleanup):
        """All 4 slates are processed and contain correct image data."""
        thread = thread_cleanup(ScanThread(
            multi_slate_environment['images_dir'],
            multi_slate_environment['cache_manager']
        ))

        with qtbot.waitSignal(thread.scan_complete, timeout=10000) as blocker:
            thread.start()

        slates_result, _message = blocker.args

        # Verify all slates have images
        for i in range(4):
            slate_name = f"slate_{i}"
            assert slate_name in slates_result, f"Missing slate: {slate_name}"
            assert len(slates_result[slate_name]['images']) == 3, (
                f"Expected 3 images in {slate_name}, got {len(slates_result[slate_name]['images'])}"
            )

        # Verify total image count
        total_images = sum(len(s['images']) for s in slates_result.values())
        assert total_images == 12

        # Verify EXIF was extracted (images should have exif key)
        for slate in slates_result.values():
            for img in slate['images']:
                assert 'exif' in img, "Images should have EXIF data"
                assert 'path' in img, "Images should have path"

    def test_parallel_progress_emissions_range(self, multi_slate_environment, qtbot, thread_cleanup):
        """Progress signals are emitted in 50-100% range during parallel EXIF processing."""
        thread = thread_cleanup(ScanThread(
            multi_slate_environment['images_dir'],
            multi_slate_environment['cache_manager']
        ))

        progress_values = []
        thread.progress.connect(lambda v: progress_values.append(v))

        with qtbot.waitSignal(thread.scan_complete, timeout=10000):
            thread.start()

        # Should have received progress values
        assert len(progress_values) > 0, "Should receive progress signals"

        # Filter for EXIF processing phase (50-100%)
        exif_progress = [v for v in progress_values if v >= 50]
        assert len(exif_progress) >= 4, (
            f"Should have at least 4 progress emissions for 4 slates, got {len(exif_progress)}"
        )

        # Should reach 100%
        assert any(v == 100 for v in progress_values), "Progress should reach 100%"

    def test_parallel_stop_event_pre_set(self, multi_slate_environment, qtbot, thread_cleanup):
        """Stop event pre-set before start results in cancellation.

        This tests that the stop mechanism works for parallel processing,
        by setting the stop event before processing begins.
        """
        thread = thread_cleanup(ScanThread(
            multi_slate_environment['images_dir'],
            multi_slate_environment['cache_manager']
        ))

        # Pre-set the stop event before starting
        thread._stop_event.set()

        with qtbot.waitSignal(thread.scan_complete, timeout=5000) as blocker:
            thread.start()

        slates_result, message = blocker.args

        # Should have been cancelled since stop was set before processing
        assert "cancelled" in message.lower(), (
            f"Expected cancellation message, got: {message}"
        )
        assert slates_result == {}, "Expected empty results when stopped"

    def test_parallel_results_written_to_slates(self, multi_slate_environment, qtbot, thread_cleanup):
        """Results from parallel processing are correctly written back to slates dict."""
        thread = thread_cleanup(ScanThread(
            multi_slate_environment['images_dir'],
            multi_slate_environment['cache_manager']
        ))

        with qtbot.waitSignal(thread.scan_complete, timeout=10000) as blocker:
            thread.start()

        slates_result, _ = blocker.args

        # Each slate should have processed images with full data
        for slate_name, slate_data in slates_result.items():
            images = slate_data.get('images', [])
            assert len(images) > 0, f"Slate {slate_name} should have images"

            for img in images:
                # Verify image has required fields from parallel processing
                assert 'path' in img
                assert 'exif' in img
                assert 'mtime' in img, "Parallel processing should add mtime"

                # Verify path is a valid string
                assert isinstance(img['path'], str)
                assert img['path'].endswith('.jpg')

    def test_parallel_exif_data_extracted(self, multi_slate_environment, qtbot, thread_cleanup):
        """EXIF data is actually extracted in parallel processing."""
        thread = thread_cleanup(ScanThread(
            multi_slate_environment['images_dir'],
            multi_slate_environment['cache_manager']
        ))

        with qtbot.waitSignal(thread.scan_complete, timeout=10000) as blocker:
            thread.start()

        slates_result, _ = blocker.args

        # Collect all focal lengths from extracted EXIF
        # Note: EXIF key is "FocalLength" (capital letters) from image_processor
        focal_lengths = []
        for slate_data in slates_result.values():
            for img in slate_data['images']:
                exif = img.get('exif', {})
                if 'FocalLength' in exif:
                    focal_lengths.append(exif['FocalLength'])

        # Should have extracted focal lengths from test images
        assert len(focal_lengths) > 0, "Should have extracted FocalLength EXIF data"

    def test_parallel_with_5_slates(self, qtbot, thread_cleanup, caplog):
        """Test parallel processing with 5 slates (more workers possible)."""
        import logging
        caplog.set_level(logging.INFO)

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            images_dir = base_path / "images"
            cache_dir = base_path / "cache"
            images_dir.mkdir()
            cache_dir.mkdir()

            # Create 5 slate directories
            for i in range(5):
                slate_dir = images_dir / f"slate_{i}"
                slate_dir.mkdir()
                for j in range(2):
                    create_real_test_image(slate_dir / f"img_{j}.jpg", focal_length=35)

            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))
            thread = thread_cleanup(ScanThread(str(images_dir), cache_manager))

            with qtbot.waitSignal(thread.scan_complete, timeout=10000) as blocker:
                thread.start()

            slates_result, message = blocker.args

            # Verify all 5 slates processed
            assert len(slates_result) == 5
            assert "complete" in message.lower()

            # Verify parallel workers were used
            worker_log = [r for r in caplog.records if "workers for slate-level" in r.message]
            assert len(worker_log) > 0, "Should log worker count"

    def test_parallel_cache_integration(self, multi_slate_environment, qtbot, thread_cleanup):
        """Verify cache is saved after parallel processing."""
        thread = thread_cleanup(ScanThread(
            multi_slate_environment['images_dir'],
            multi_slate_environment['cache_manager']
        ))

        with qtbot.waitSignal(thread.scan_complete, timeout=10000) as blocker:
            thread.start()

        slates_result, _ = blocker.args

        # Verify cache was saved
        cached = multi_slate_environment['cache_manager'].load_cache(
            multi_slate_environment['images_dir']
        )
        assert cached is not None, "Cache should have been saved"
        assert len(cached) == 4, "Cache should contain all 4 slates"

        # Verify cached data matches results
        assert cached == slates_result

    def test_parallel_error_does_not_crash(self, qtbot, thread_cleanup, caplog):
        """Error in one slate during parallel processing doesn't crash the thread."""
        import logging
        caplog.set_level(logging.DEBUG)

        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            images_dir = base_path / "images"
            cache_dir = base_path / "cache"
            images_dir.mkdir()
            cache_dir.mkdir()

            # Create 4 slate directories - one with a corrupt/unreadable file
            for i in range(4):
                slate_dir = images_dir / f"slate_{i}"
                slate_dir.mkdir()
                if i == 2:
                    # Create a corrupted "image" file that will fail EXIF extraction
                    corrupt_file = slate_dir / "corrupt.jpg"
                    corrupt_file.write_bytes(b"not a valid image")
                else:
                    # Create valid images
                    for j in range(2):
                        create_real_test_image(slate_dir / f"img_{j}.jpg", focal_length=35)

            cache_manager = ImprovedCacheManager(base_dir=str(cache_dir))
            thread = thread_cleanup(ScanThread(str(images_dir), cache_manager))

            with qtbot.waitSignal(thread.scan_complete, timeout=10000) as blocker:
                thread.start()

            slates_result, message = blocker.args

            # Thread should still complete (not crash)
            assert "complete" in message.lower(), f"Expected completion, got: {message}"

            # Other slates should have been processed successfully
            valid_slates = ['slate_0', 'slate_1', 'slate_3']
            for slate_name in valid_slates:
                assert slate_name in slates_result, f"Expected {slate_name} to be processed"
