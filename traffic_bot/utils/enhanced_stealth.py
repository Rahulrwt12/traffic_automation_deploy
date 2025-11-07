"""Enhanced stealth module for advanced detection avoidance"""
import random
import logging
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class EnhancedStealth:
    """Advanced stealth techniques to reduce detection footprint"""
    
    def __init__(self, config: dict):
        """
        Initialize enhanced stealth module
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.enabled = config.get('stealth_mode', True)
        
        # Advanced stealth settings
        stealth_config = config.get('advanced_stealth', {})
        self.mask_canvas = stealth_config.get('mask_canvas', True)
        self.mask_webgl = stealth_config.get('mask_webgl', True)
        self.randomize_headers = stealth_config.get('randomize_headers', True)
        self.humanize_timing = stealth_config.get('humanize_timing', True)
    
    def get_enhanced_stealth_script(self) -> str:
        """
        Get enhanced stealth script with advanced detection avoidance
        
        Returns:
            JavaScript code for stealth injection
        """
        return """
        // Enhanced WebDriver detection removal
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Override plugins with realistic values
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    {name: 'Chrome PDF Plugin', description: 'Portable Document Format', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', description: '', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                    {name: 'Native Client', description: '', filename: 'internal-nacl-plugin'}
                ];
                return plugins;
            }
        });
        
        // Override languages with realistic array
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        // Override platform
        Object.defineProperty(navigator, 'platform', {
            get: () => navigator.platform || 'Win32'
        });
        
        // Override hardware concurrency
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => Math.max(2, navigator.hardwareConcurrency || 4)
        });
        
        // Override device memory
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => Math.max(2, navigator.deviceMemory || 8)
        });
        
        // Chrome object
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Canvas fingerprint masking
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            const context = this.getContext('2d');
            if (context) {
                const imageData = context.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] += Math.floor(Math.random() * 10) - 5;
                }
                context.putImageData(imageData, 0, 0);
            }
            return originalToDataURL.apply(this, arguments);
        };
        
        // WebGL fingerprint masking
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) { // UNMASKED_VENDOR_WEBGL
                return 'Intel Inc.';
            }
            if (parameter === 37446) { // UNMASKED_RENDERER_WEBGL
                return 'Intel Iris OpenGL Engine';
            }
            return getParameter.apply(this, arguments);
        };
        
        // AudioContext fingerprint masking
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {
            const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
            AudioContext.prototype.createAnalyser = function() {
                const analyser = originalCreateAnalyser.apply(this, arguments);
                const originalGetFloatFrequencyData = analyser.getFloatFrequencyData;
                analyser.getFloatFrequencyData = function(array) {
                    originalGetFloatFrequencyData.apply(this, arguments);
                    for (let i = 0; i < array.length; i++) {
                        array[i] += Math.random() * 0.0001;
                    }
                };
                return analyser;
            };
        }
        
        // Battery API spoofing
        if (navigator.getBattery) {
            const originalGetBattery = navigator.getBattery;
            navigator.getBattery = function() {
                return originalGetBattery.call(this).then(battery => {
                    Object.defineProperty(battery, 'charging', { get: () => true });
                    Object.defineProperty(battery, 'level', { get: () => Math.random() * 0.3 + 0.7 });
                    return battery;
                });
            };
        }
        
        // Notification API spoofing
        if (Notification) {
            const originalPermission = Notification.permission;
            Object.defineProperty(Notification, 'permission', {
                get: () => 'default'
            });
        }
        
        // MediaDevices fingerprint masking
        if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
            const originalEnumerateDevices = navigator.mediaDevices.enumerateDevices;
            navigator.mediaDevices.enumerateDevices = function() {
                return originalEnumerateDevices.apply(this, arguments).then(devices => {
                    return devices.map(device => ({
                        ...device,
                        deviceId: device.deviceId + Math.random().toString(36).substring(7)
                    }));
                });
            };
        }
        
        // Remove automation indicators
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """
    
    def generate_random_headers(self, base_headers: Dict[str, str] = None) -> Dict[str, str]:
        """
        Generate randomized HTTP headers to reduce fingerprinting
        
        Args:
            base_headers: Base headers to modify
            
        Returns:
            Dictionary of randomized headers
        """
        if not self.randomize_headers:
            return base_headers or {}
        
        # Common Accept headers variations
        accept_variations = [
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
        ]
        
        # Accept-Language variations
        language_variations = [
            'en-US,en;q=0.9',
            'en-US,en;q=0.9,fr;q=0.8',
            'en-GB,en-US;q=0.9,en;q=0.8',
            'en-US,en;q=0.9,es;q=0.8'
        ]
        
        # Accept-Encoding variations
        encoding_variations = [
            'gzip, deflate, br',
            'gzip, deflate',
            'gzip, deflate, br, zstd'
        ]
        
        headers = base_headers.copy() if base_headers else {}
        
        # Randomize Accept headers
        headers['Accept'] = random.choice(accept_variations)
        headers['Accept-Language'] = random.choice(language_variations)
        headers['Accept-Encoding'] = random.choice(encoding_variations)
        
        # Add DNT header sometimes
        if random.random() < 0.7:
            headers['DNT'] = '1'
        
        # Add Sec-Fetch headers (Chrome specific)
        if random.random() < 0.8:
            headers['Sec-Fetch-Dest'] = 'document'
            headers['Sec-Fetch-Mode'] = 'navigate'
            headers['Sec-Fetch-Site'] = random.choice(['none', 'same-origin', 'cross-site'])
            headers['Sec-Fetch-User'] = '?1'
        
        # Add Upgrade-Insecure-Requests sometimes
        if random.random() < 0.6:
            headers['Upgrade-Insecure-Requests'] = '1'
        
        # Add Connection header
        headers['Connection'] = 'keep-alive'
        
        return headers
    
    def humanize_timing(self, base_delay: float, variation: float = 0.3) -> float:
        """
        Add human-like timing variations to reduce detection
        
        Args:
            base_delay: Base delay in seconds
            variation: Variation percentage (0.0 to 1.0)
            
        Returns:
            Humanized delay with random variation
        """
        if not self.humanize_timing:
            return base_delay
        
        # Use normal distribution for more natural timing
        variance = base_delay * variation
        delay = base_delay + random.gauss(0, variance / 3)
        
        # Ensure minimum delay
        return max(0.1, delay)
    
    def get_connection_timing(self) -> Dict[str, float]:
        """
        Get realistic connection timing values for performance API
        
        Returns:
            Dictionary with timing values
        """
        return {
            'connectStart': random.uniform(10, 50),
            'connectEnd': random.uniform(50, 150),
            'domainLookupStart': random.uniform(5, 30),
            'domainLookupEnd': random.uniform(30, 80),
            'fetchStart': random.uniform(0, 10),
            'responseStart': random.uniform(100, 300),
            'responseEnd': random.uniform(200, 500)
        }

