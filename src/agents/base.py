"""
Base agent class for all autonomous agents.

Provides common infrastructure for agent lifecycle management,
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                self.logger.info(f"Agent '{self.name}' process loop cancelled")
                break
            
            except Exception as e:
                self._error_count += 1
                self.logger.error(
                    f"Error in agent '{self.name}' process loop "
                    f"(error {self._error_count}/{self._max_consecutive_errors}): {e}",
                    exc_info=True
                )
                
                # If too many consecutive errors, stop agent
                if self._error_count >= self._max_consecutive_errors:
                    self.logger.critical(
                        f"Agent '{self.name}' exceeded max consecutive errors, stopping"
                    )
                    self.running = False
                    break
                
                # Backoff before retry
                await asyncio.sleep(min(2 ** self._error_count, 60))
            
            # Small yield to event loop
            await asyncio.sleep(0.1)
        
        self.logger.info(f"Agent '{self.name}' process loop exited")
    
    def __repr__(self) -> str:
        """String representation of agent."""
        return f"{self.__class__.__name__}(name='{self.name}', running={self.running})"
