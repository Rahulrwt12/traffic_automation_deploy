"""Realistic user behavior simulation for browser automation"""
import random
import asyncio
import logging
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class UserBehavior:
    """Simulates realistic user behavior in browser"""
    
    def __init__(self, config: dict):
        """
        Initialize user behavior simulator
        
        Args:
            config: Behavior configuration
        """
        self.config = config
        self.mouse_movements = config.get('mouse_movements', True)
        self.scrolling = config.get('scrolling', True)
        self.click_interactions = config.get('click_interactions', True)
        self.scroll_pattern = config.get('scroll_pattern', 'progressive')
        self.mouse_movement_chance = config.get('mouse_movement_chance', 0.7)
        self.click_chance = config.get('click_chance', 0.3)
        self.scroll_delay_min = config.get('scroll_delay_min', 0.5)
        self.scroll_delay_max = config.get('scroll_delay_max', 2.0)
    
    async def handle_cookie_consent(self, page: Page):
        """Handle cookie consent banners by accepting them"""
        try:
            # Common selectors for cookie consent "Accept All" buttons
            cookie_selectors = [
                # Text-based selectors (most reliable)
                'button:has-text("Accept All")',
                'button:has-text("Accept All Cookies")',
                'button:has-text("Accept all")',
                'button:has-text("Accept all cookies")',
                'a:has-text("Accept All")',
                'a:has-text("Accept All Cookies")',
                # Common class/id patterns
                'button[id*="accept"]',
                'button[class*="accept"]',
                'button[class*="cookie"][class*="accept"]',
                'button[id*="cookie"][id*="accept"]',
                '#onetrust-accept-btn-handler',
                '#accept-all-cookies',
                '.cookie-accept',
                '.accept-cookies',
                '.accept-all',
                # Generic patterns
                'button[aria-label*="Accept"]',
                'button[aria-label*="accept"]'
            ]
            
            # Try each selector with a short timeout
            for selector in cookie_selectors:
                try:
                    # Wait for the element with a short timeout
                    element = await page.wait_for_selector(selector, timeout=2000, state='visible')
                    if element:
                        logger.info(f"Cookie consent banner found, clicking: {selector}")
                        # Scroll into view and click
                        await element.scroll_into_view_if_needed()
                        await asyncio.sleep(0.3)
                        await element.click()
                        logger.info("✅ Cookie consent accepted")
                        # Wait a moment for the banner to disappear
                        await asyncio.sleep(1.0)
                        return True
                except Exception:
                    continue
            
            logger.debug("No cookie consent banner found (this is normal if already accepted)")
            return False
            
        except Exception as e:
            logger.debug(f"Cookie consent handling error: {e}")
            return False
    
    async def simulate_mouse_movements(self, page: Page, num_movements: int = 3):
        """Simulate random mouse movements"""
        if not self.mouse_movements:
            return
        
        if random.random() > self.mouse_movement_chance:
            return
        
        try:
            viewport = page.viewport_size
            if not viewport:
                return
            
            width = viewport['width']
            height = viewport['height']
            
            for _ in range(num_movements):
                x = random.randint(0, width)
                y = random.randint(0, height)
                
                # Move mouse with slight delay
                await page.mouse.move(x, y, steps=random.randint(5, 15))
                await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            logger.debug(f"Mouse movement simulation error: {e}")
    
    async def simulate_scrolling(self, page: Page):
        """Simulate realistic scrolling behavior"""
        if not self.scrolling:
            return
        
        try:
            viewport = page.viewport_size
            if not viewport:
                return
            
            height = viewport['height']
            content_height = await page.evaluate("document.body.scrollHeight")
            
            if content_height <= height:
                return  # No scrolling needed
            
            if self.scroll_pattern == 'progressive':
                # Progressive scroll down
                scroll_steps = random.randint(3, 8)
                scroll_distance = content_height / scroll_steps
                
                for i in range(scroll_steps):
                    scroll_to = min((i + 1) * scroll_distance, content_height)
                    await page.evaluate(f"window.scrollTo({{top: {scroll_to}, behavior: 'smooth'}})")
                    await asyncio.sleep(random.uniform(self.scroll_delay_min, self.scroll_delay_max))
                    
                    # Occasionally scroll back up a bit
                    if random.random() < 0.2:
                        back_scroll = random.randint(50, 200)
                        current_pos = await page.evaluate("window.pageYOffset")
                        new_pos = max(0, current_pos - back_scroll)
                        await page.evaluate(f"window.scrollTo({{top: {new_pos}, behavior: 'smooth'}})")
                        await asyncio.sleep(random.uniform(0.3, 0.8))
            
            elif self.scroll_pattern == 'random':
                # Random scroll positions
                for _ in range(random.randint(2, 5)):
                    scroll_to = random.randint(0, int(content_height))
                    await page.evaluate(f"window.scrollTo({{top: {scroll_to}, behavior: 'smooth'}})")
                    await asyncio.sleep(random.uniform(self.scroll_delay_min, self.scroll_delay_max))
            
            # Scroll back to top or stay at bottom
            if random.random() < 0.3:
                await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
                await asyncio.sleep(0.5)
            else:
                # Stay at bottom
                await page.evaluate(f"window.scrollTo({{top: {content_height}, behavior: 'smooth'}})")
                await asyncio.sleep(0.5)
        
        except Exception as e:
            logger.debug(f"Scrolling simulation error: {e}")
    
    async def simulate_clicks(self, page: Page):
        """Simulate random clicks on elements"""
        if not self.click_interactions:
            return
        
        if random.random() > self.click_chance:
            return
        
        try:
            # Find clickable elements
            clickable_selectors = [
                'a[href]',
                'button:not([disabled])',
                'img[onclick]',
                '.product-image',
                '.cta-button',
                '.view-details'
            ]
            
            clicked = False
            for selector in clickable_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        # Randomly select one element
                        element = random.choice(elements)
                        
                        # Check if element is visible
                        is_visible = await element.is_visible()
                        if is_visible:
                            # Scroll element into view
                            await element.scroll_into_view_if_needed()
                            await asyncio.sleep(random.uniform(0.3, 0.7))
                            
                            # Click the element
                            await element.click(timeout=2000)
                            clicked = True
                            await asyncio.sleep(random.uniform(0.5, 1.5))
                            break
                except Exception:
                    continue
            
            if not clicked:
                # Click on random position if no clickable elements found
                viewport = page.viewport_size
                if viewport:
                    x = random.randint(100, viewport['width'] - 100)
                    y = random.randint(100, viewport['height'] - 100)
                    await page.mouse.click(x, y)
                    await asyncio.sleep(random.uniform(0.3, 0.7))
        
        except Exception as e:
            logger.debug(f"Click simulation error: {e}")
    
    async def simulate_reading_time(self, page: Page, min_time: float, max_time: float):
        """Simulate reading time with behavior"""
        reading_time = random.uniform(min_time, max_time)
        
        # Break reading time into segments with behavior
        segments = random.randint(2, 4)
        segment_time = reading_time / segments
        
        for i in range(segments):
            # Mouse movement occasionally
            if random.random() < 0.4:
                await self.simulate_mouse_movements(page, num_movements=1)
            
            # Scroll during reading
            if i > 0 and random.random() < 0.6:
                await self.simulate_scrolling(page)
            
            # Wait for segment
            await asyncio.sleep(segment_time)
        
        # Final scroll and possible click
        if random.random() < 0.5:
            await self.simulate_scrolling(page)
        
        if random.random() < 0.3:
            await self.simulate_clicks(page)
    
    async def simulate_full_session(self, page: Page, reading_time: float):
        """Simulate complete realistic user session"""
        try:
            # Handle cookie consent first (if present)
            await self.handle_cookie_consent(page)
            
            # Initial mouse movement
            await self.simulate_mouse_movements(page, num_movements=2)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Scroll through page
            await self.simulate_scrolling(page)
            
            # Reading time with occasional interactions
            await self.simulate_reading_time(page, reading_time * 0.6, reading_time * 1.4)
            
        except Exception as e:
            logger.debug(f"Full session simulation error: {e}")

