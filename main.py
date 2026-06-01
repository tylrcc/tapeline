"""
sim/gen_vectors.py - Vector generation from recorded tick data and synthetic random walk.

This module provides functionality to generate price-volume vectors from both
real recorded tick data (CSV format) and synthetic random walk data. The real
data helps test edge cases that synthetic data might miss, such as gap-ups,
fat block prints, and zero-volume runs.
"""

import csv
import os
from typing import List, Tuple, Optional, Iterator, Union
from dataclasses import dataclass
import random
import math
from pathlib import Path


@dataclass
class Tick:
    """Represents a single tick with price and volume."""
    price: float
    volume: int


@dataclass
class Vector:
    """
    Represents a price-volume vector.
    Format: (price_change, volume, is_synthetic)
    """
    price_change: float
    volume: int
    is_synthetic: bool

    def __post_init__(self):
        """Validate vector components."""
        if not isinstance(self.price_change, (int, float)):
            raise TypeError("price_change must be numeric")
        if not isinstance(self.volume, int) or self.volume < 0:
            raise ValueError("volume must be a non-negative integer")
        if not isinstance(self.is_synthetic, bool):
            raise TypeError("is_synthetic must be boolean")


class TickDataReader:
    """Reads tick data from CSV files with error handling."""
    
    REQUIRED_COLUMNS = {'price', 'volume'}
    
    def __init__(self, csv_path: Union[str, Path]):
        """
        Initialize the reader with a CSV file path.
        
        Args:
            csv_path: Path to the CSV file containing tick data
            
        Raises:
            FileNotFoundError: If the CSV file doesn't exist
            ValueError: If the CSV file has invalid format
        """
        self.csv_path = Path(csv_path)
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Validate CSV structure
        self._validate_csv()
    
    def _validate_csv(self) -> None:
        """Validate that the CSV file has the required columns."""
        try:
            with open(self.csv_path, 'r') as f:
                reader = csv.reader(f)
                header = next(reader)
                header_lower = [col.strip().lower() for col in header]
                
                if not self.REQUIRED_COLUMNS.issubset(set(header_lower)):
                    missing = self.REQUIRED_COLUMNS - set(header_lower)
                    raise ValueError(
                        f"CSV missing required columns: {missing}. "
                        f"Found columns: {header_lower}"
                    )
        except StopIteration:
            raise ValueError("CSV file is empty")
        except csv.Error as e:
            raise ValueError(f"Error reading CSV file: {e}")
    
    def read_ticks(self) -> Iterator[Tick]:
        """
        Read tick data from the CSV file.
        
        Yields:
            Tick objects with price and volume data
            
        Raises:
            ValueError: If data rows contain invalid values
        """
        with open(self.csv_path, 'r') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):  # Start from row 2 (after header)
                try:
                    price = float(row['price'].strip())
                    volume = int(row['volume'].strip())
                    
                    if volume < 0:
                        print(f"Warning: Negative volume at row {row_num}, setting to 0")
                        volume = 0
                    
                    yield Tick(price=price, volume=volume)
                    
                except (ValueError, KeyError) as e:
                    print(f"Warning: Invalid data at row {row_num}: {e}")
                    continue


class SyntheticTickGenerator:
    """Generates synthetic tick data using random walk."""
    
    def __init__(self, 
                 start_price: float = 100.0,
                 volatility: float = 0.01,
                 base_volume: int = 1000,
                 volume_noise: float = 0.3):
        """
        Initialize the synthetic generator.
        
        Args:
            start_price: Initial price for the random walk
            volatility: Standard deviation of price changes (as fraction)
            base_volume: Base volume for each tick
            volume_noise: Fraction of volume noise (0 to 1)
        """
        self.current_price = start_price
        self.volatility = volatility
        self.base_volume = base_volume
        self.volume_noise = volume_noise
    
    def generate_tick(self) -> Tick:
        """
        Generate a single synthetic tick.
        
        Returns:
            A Tick object with random walk price and noisy volume
        """
        # Random walk price change (log-normal)
        price_change = random.gauss(0, self.volatility)
        self.current_price *= (1 + price_change)
        
        # Volume with noise
        volume_noise_factor = 1 + random.uniform(-self.volume_noise, self.volume_noise)
        volume = max(0, int(self.base_volume * volume_noise_factor))
        
        return Tick(price=self.current_price, volume=volume)


class VectorGenerator:
    """
    Generates price-volume vectors from tick data.
    
    Vectors represent changes between consecutive ticks, making them
    suitable for analysis of market microstructure.
    """
    
    def __init__(self, max_volume: Optional[int] = None):
        """
        Initialize the vector generator.
        
        Args:
            max_volume: Maximum allowed volume (None for no limit)
        """
        self.max_volume = max_volume
        self.last_tick: Optional[Tick] = None
    
    def reset(self) -> None:
        """Reset the generator state."""
        self.last_tick = None
    
    def tick_to_vector(self, tick: Tick, is_synthetic: bool = False) -> Optional[Vector]:
        """
        Convert a tick to a vector based on change from last tick.
        
        Args:
            tick: Current tick data
            is_synthetic: Whether this tick comes from synthetic data
            
        Returns:
            Vector object or None if this is the first tick
        """
        if self.last_tick is None:
            self.last_tick = tick
            return None
        
        # Calculate price change
        if self.last_tick.price > 0:
            price_change = (tick.price - self.last_tick.price) / self.last_tick.price
        else:
            price_change = 0.0
        
        # Cap volume if needed
        volume = tick.volume
        if self.max_volume is not None:
            volume = min(volume, self.max_volume)
        
        self.last_tick = tick
        
        return Vector(
            price_change=price_change,
            volume=volume,
            is_synthetic=is_synthetic
        )
    
    def generate_vectors_from_csv(self, csv_path: Union[str, Path]) -> Iterator[Vector]:
        """
        Generate vectors from a CSV file of tick data.
        
        Args:
            csv_path: Path to the CSV file
            
        Yields:
            Vector objects for each tick pair
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
        """
        self.reset()
        reader = TickDataReader(csv_path)
        
        for tick in reader.read_ticks():
            vector = self.tick_to_vector(tick, is_synthetic=False)
            if vector is not None:
                yield vector
    
    def generate_synthetic_vectors(self, 
                                  num_ticks: int,
                                  **synthetic_kwargs) -> Iterator[Vector]:
        """
        Generate synthetic vectors using random walk.
        
        Args:
            num_ticks: Number of synthetic ticks to generate
            **synthetic_kwargs: Arguments for SyntheticTickGenerator
            
        Yields:
            Vector objects for each synthetic tick pair
        """
        self.reset()
        generator = SyntheticTickGenerator(**synthetic_kwargs)
        
        for _ in range(num_ticks):
            tick = generator.generate_tick()
            vector = self.tick_to_vector(tick, is_synthetic=True)
            if vector is not None:
                yield vector


def main():
    """
    Main entry point for the vector generation script.
    
    Demonstrates usage with both synthetic and real data.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate price-volume vectors from tick data"
    )
    parser.add_argument(
        '--csv', '-c',
        type=str,
        help='Path to CSV file with recorded tick data (price, volume)'
    )
    parser.add_argument(
        '--synthetic', '-s',
        type=int,
        default=100,
        help='Number of synthetic ticks to generate (default: 100)'
    )
    parser.add_argument(
        '--max-volume',
        type=int,
        help='Maximum volume to include in vectors'
    )
    
    args = parser.parse_args()
    
    generator = VectorGenerator(max_volume=args.max_volume)
    
    # Generate synthetic vectors
    print("Generating synthetic vectors...")
    synthetic_count = 0
    for vector in generator.generate_synthetic_vectors(args.synthetic):
        synthetic_count += 1
        print(f"  Synthetic vector {synthetic_count}: "
              f"price_change={vector.price_change:.6f}, "
              f"volume={vector.volume}")
    
    # Generate vectors from CSV if provided
    if args.csv:
        print(f"\nGenerating vectors from CSV: {args.csv}")
        try:
            csv_count = 0
            for vector in generator.generate_vectors_from_csv(args.csv):
                csv_count += 1
                print(f"  CSV vector {csv_count}: "
                      f"price_change={vector.price_change:.6f}, "
                      f"volume={vector.volume}")
            
            if csv_count == 0:
                print("  No vectors generated from CSV (need at least 2 ticks)")
                
        except (FileNotFoundError, ValueError) as e:
            print(f"Error reading CSV: {e}")
    
    print(f"\nTotal synthetic vectors: {synthetic_count}")
    if args.csv:
        print(f"Total CSV vectors: {csv_count}")


if __name__ == "__main__":
    main()