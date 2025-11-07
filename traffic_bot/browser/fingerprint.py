"""Browser fingerprint randomization for detection avoidance"""
import random
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class FingerprintGenerator:
    """Generates randomized browser fingerprints"""
    
    # Common screen resolutions
    DESKTOP_RESOLUTIONS = [
        (1920, 1080), (1366, 768), (1536, 864), (1440, 900),
        (1280, 1024), (1600, 900), (1920, 1200), (2560, 1440)
    ]
    
    MOBILE_RESOLUTIONS = [
        (375, 667), (390, 844), (414, 896), (428, 926),
        (360, 640), (412, 915), (393, 851)
    ]
    
    TABLET_RESOLUTIONS = [
        (768, 1024), (810, 1080), (834, 1194), (1024, 1366)
    ]
    
    # Timezones
    TIMEZONES = [
        'America/New_York', 'America/Chicago', 'America/Denver',
        'America/Los_Angeles', 'Europe/London', 'Europe/Paris',
        'Europe/Berlin', 'Asia/Tokyo', 'Asia/Shanghai',
        'Australia/Sydney', 'America/Toronto', 'America/Vancouver'
    ]
    
    # Languages
    LANGUAGES = [
        'en-US', 'en-GB', 'en-CA', 'en-AU',
        'fr-FR', 'de-DE', 'es-ES', 'it-IT',
        'ja-JP', 'zh-CN', 'ko-KR', 'pt-BR'
    ]
    
    # Platform variations
    PLATFORMS = {
        'Windows': ['Win32', 'Win64'],
        'MacIntel': ['Intel Mac OS X 10_15_7', 'Intel Mac OS X 11_0_0'],
        'Linux x86_64': ['Linux x86_64']
    }
    
    # Hardware concurrency (CPU cores)
    CPU_CORES = [2, 4, 6, 8, 12, 16]
    
    # Device memory (GB)
    DEVICE_MEMORY = [2, 4, 8, 16, 32]
    
    def __init__(self, device_type: str = 'desktop'):
        """
        Initialize fingerprint generator
        
        Args:
            device_type: 'desktop', 'mobile', or 'tablet'
        """
        self.device_type = device_type
    
    def generate_viewport(self) -> Dict[str, int]:
        """Generate random viewport size"""
        if self.device_type == 'mobile':
            width, height = random.choice(self.MOBILE_RESOLUTIONS)
        elif self.device_type == 'tablet':
            width, height = random.choice(self.TABLET_RESOLUTIONS)
        else:
            width, height = random.choice(self.DESKTOP_RESOLUTIONS)
        
        return {
            'width': width,
            'height': height,
            'device_scale_factor': random.choice([1, 2]) if self.device_type == 'mobile' else 1
        }
    
    def generate_timezone(self) -> str:
        """Generate random timezone"""
        return random.choice(self.TIMEZONES)
    
    def generate_language(self) -> str:
        """Generate random language"""
        return random.choice(self.LANGUAGES)
    
    def generate_platform(self) -> str:
        """Generate random platform"""
        platform = random.choice(list(self.PLATFORMS.keys()))
        if platform in self.PLATFORMS:
            return random.choice(self.PLATFORMS[platform])
        return platform
    
    def generate_hardware_concurrency(self) -> int:
        """Generate random CPU cores"""
        return random.choice(self.CPU_CORES)
    
    def generate_device_memory(self) -> int:
        """Generate random device memory in GB"""
        return random.choice(self.DEVICE_MEMORY)
    
    def generate_webgl_vendor(self) -> Dict[str, str]:
        """Generate WebGL vendor/renderer (for fingerprinting)"""
        vendors = [
            {'vendor': 'Google Inc. (Intel)', 'renderer': 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)'},
            {'vendor': 'Google Inc. (NVIDIA)', 'renderer': 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 Direct3D11 vs_5_0 ps_5_0, D3D11)'},
            {'vendor': 'Google Inc. (AMD)', 'renderer': 'ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0, D3D11)'},
            {'vendor': 'Google Inc.', 'renderer': 'ANGLE (Google, Vulkan 1.2.0 (SwiftShader Device (Subzero)), SwiftShader driver)'},
        ]
        
        mobile_vendors = [
            {'vendor': 'Apple Inc. (Apple GPU)', 'renderer': 'Apple GPU'},
            {'vendor': 'Google Inc. (Qualcomm)', 'renderer': 'Adreno (TM) 640'},
            {'vendor': 'Google Inc. (ARM)', 'renderer': 'Mali-G78 MP24'},
        ]
        
        if self.device_type == 'mobile':
            return random.choice(mobile_vendors)
        return random.choice(vendors)
    
    def generate_full_fingerprint(self) -> Dict[str, Any]:
        """Generate complete browser fingerprint"""
        viewport = self.generate_viewport()
        webgl = self.generate_webgl_vendor()
        
        return {
            'viewport': viewport,
            'timezone': self.generate_timezone(),
            'language': self.generate_language(),
            'platform': self.generate_platform(),
            'hardware_concurrency': self.generate_hardware_concurrency(),
            'device_memory': self.generate_device_memory(),
            'webgl_vendor': webgl['vendor'],
            'webgl_renderer': webgl['renderer'],
            'device_type': self.device_type
        }

