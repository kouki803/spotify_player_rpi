from PIL import Image, ImageDraw, ImageFont


from spotify_player_rpi.hardware_controller import HardwareController


class DisplayManager:
    IS_RPI = HardwareController.IS_RPI # Raspberry Pi環境かどうかを示すフラグ

    def __init__(self):
        self.epd = epd2in13_V2.EPD()
        self.epd.init()
        self.epd.Clear(0xFF) # Clear display with white background (0xFF for white, 0x00 for black)
        self.width = self.epd.width
        self.height = self.epd.height
        
        # Load fonts (adjust paths and font names as per your Raspberry Pi OS)
        try:
            # Common font paths on Raspberry Pi OS
            self.font_large = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
            self.font_medium = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
            self.font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 10)
        except IOError:
            print("Warning: Font not found. Using default font.")
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def display_info(self, track_name, artist_name, qr_code_image=None):
        # Create a new image with white background
        # '1' mode for 1-bit pixels (black and white)
        image = Image.new('1', (self.width, self.height), 255) # 255: white background
        draw = ImageDraw.Draw(image)

        # Display track name and artist name
        # Adjust text position based on display size and font
        draw.text((5, 5), track_name, font=self.font_large, fill=0) # fill=0: black text
        draw.text((5, 30), artist_name, font=self.font_medium, fill=0)

        # Display QR code if provided
        if qr_code_image:
            # Resize QR code image to fit a portion of the e-ink display
            # Adjust qr_size based on your preference and display layout
            qr_size = min(self.width, self.height) // 2 - 10 # Example: about half the screen, with some margin
            qr_code_image = qr_code_image.resize((qr_size, qr_size))
            
            # Position the QR code (e.g., bottom-right)
            x_offset = self.width - qr_size - 5 # 5px margin from right
            y_offset = self.height - qr_size - 5 # 5px margin from bottom
            
            image.paste(qr_code_image, (x_offset, y_offset))

        # Send the image buffer to the e-ink display
        self.epd.display(self.epd.getbuffer(image))

    def clear_display(self):
        """Clears the e-ink display."""
        self.epd.Clear(0xFF) # Clear with white

    def sleep(self):
        """Puts the e-ink display into low power sleep mode."""
        print("e-ink display going to sleep...")
        self.epd.sleep()

    def wake_up(self):
        """Wakes up the e-ink display from sleep mode."""
        print("e-ink display waking up...")
        self.epd.init() # Re-initialize the display

    def close(self):
        """Cleans up e-ink display resources."""
        print("Closing e-ink display.")
        self.epd.Dev_exit() # Proper exit for Waveshare library
