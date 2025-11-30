import cmd
import sys
import json
from datetime import datetime
from typing import Optional

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS_ENABLED = True
except ImportError:
    COLORS_ENABLED = False
    # Fallback if colorama not installed
    class Fore:
        RED = GREEN = YELLOW = BLUE = CYAN = MAGENTA = WHITE = RESET = ''
    class Style:
        BRIGHT = DIM = RESET_ALL = ''

from .storage import StorageEngine
from .cache import PredictiveCache
from .anomaly import AnomalyDetector
from .archival import ArchiveManager
from .recovery import RecoveryManager, OperationType


class SmartStoreDBCLI(cmd.Cmd):
    """Interactive CLI for SmartStoreDB"""
    
    intro = f"""
{Fore.CYAN}╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║            {Fore.GREEN}SmartStoreDB v1.0{Fore.CYAN}                            ║
║     {Fore.WHITE}Intelligent Key-Value Store with ML{Fore.CYAN}              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝{Style.RESET_ALL}

Type 'help' or '?' to list commands.
Type 'help <command>' for detailed information.
"""
    
    prompt = f"{Fore.GREEN}SmartStoreDB>{Style.RESET_ALL} "
    
    def __init__(self):
        super().__init__()
        
        # Initialize components
        print(f"{Fore.YELLOW}Initializing SmartStoreDB...{Style.RESET_ALL}")
        
        self.storage = StorageEngine(data_dir="./data")
        self.cache = PredictiveCache(cache_size=1000)
        self.anomaly_detector = AnomalyDetector()
        self.archive_manager = ArchiveManager()
        self.recovery_manager = RecoveryManager()
        
        # Perform recovery if needed
        self.recovery_manager.recover(self.storage)
        
        print(f"{Fore.GREEN}✓ SmartStoreDB initialized successfully{Style.RESET_ALL}\n")
    
    # ===== Key-Value Operations =====
    
    def do_put(self, arg):
        """
        Store a key-value pair
        Usage: put <key> <value> [ttl=<seconds>] [type=<string|number|json|list>]
        
        Examples:
            put username john
            put session_id abc123 ttl=3600
            put config {"debug": true} type=json
        """
        args = arg.split()
        if len(args) < 2:
            print(f"{Fore.RED}Error: Usage: put <key> <value> [ttl=<seconds>] [type=<type>]{Style.RESET_ALL}")
            return
        
        key = args[0]
        value = args[1]
        ttl = None
        data_type = "string"
        
        # Parse optional parameters
        for param in args[2:]:
            if param.startswith("ttl="):
                try:
                    ttl = int(param.split("=")[1])
                except ValueError:
                    print(f"{Fore.RED}Error: TTL must be an integer{Style.RESET_ALL}")
                    return
            elif param.startswith("type="):
                data_type = param.split("=")[1]
        
        # Convert value based on type
        try:
            if data_type == "number":
                value = float(value)
            elif data_type == "json":
                try:
                    # Convert single quotes to double quotes
                    cleaned = value.replace("'", '"')
                    value = json.loads(cleaned)
                except json.JSONDecodeError:
                    print(f"{Fore.RED}Error: Invalid JSON format{Style.RESET_ALL}")
                    return

        except:
            print(f"{Fore.RED}Error: Invalid value format for type '{data_type}'{Style.RESET_ALL}")
            return
        
        # Store the key
        start_time = datetime.now()
        success = self.storage.put(key, value, ttl, data_type)
        latency = (datetime.now() - start_time).total_seconds() * 1000
        
        if success:
            # Log to recovery manager
            self.recovery_manager.log_operation(
                OperationType.PUT, key, value, 
                {'ttl': ttl, 'data_type': data_type}
            )
            
            # Record for anomaly detection
            self.anomaly_detector.record_access(success=True, latency_ms=latency)
            
            print(f"{Fore.GREEN}✓ Stored: {key} = {value}{Style.RESET_ALL}")
            if ttl:
                print(f"  {Fore.CYAN}TTL: {ttl} seconds{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Failed to store key{Style.RESET_ALL}")
            self.anomaly_detector.record_access(success=False)
    
    def do_get(self, arg):
        """
        Retrieve a value by key
        Usage: get <key>
        
        Examples:
            get username
            get session_id
        """
        if not arg:
            print(f"{Fore.RED}Error: Usage: get <key>{Style.RESET_ALL}")
            return
        
        key = arg.strip()
        
        # Try cache first
        start_time = datetime.now()
        value = self.cache.get_from_cache(key)
        cache_hit = value is not None
        
        if not cache_hit:
            value = self.storage.get(key)
        
        latency = (datetime.now() - start_time).total_seconds() * 1000
        
        # Record access
        self.cache.record_access(key, value)
        self.anomaly_detector.record_access(success=value is not None, latency_ms=latency)
        
        if value is not None:
            source = "cache" if cache_hit else "storage"
            print(f"{Fore.GREEN}✓ {key} = {value}{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}Source: {source} | Latency: {latency:.2f}ms{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠ Key '{key}' not found{Style.RESET_ALL}")
    
    def do_delete(self, arg):
        """
        Delete a key
        Usage: delete <key>
        
        Examples:
            delete username
            delete temp_data
        """
        if not arg:
            print(f"{Fore.RED}Error: Usage: delete <key>{Style.RESET_ALL}")
            return
        
        key = arg.strip()
        success = self.storage.delete(key)
        
        if success:
            # Log to recovery manager
            self.recovery_manager.log_operation(OperationType.DELETE, key)
            
            print(f"{Fore.GREEN}✓ Deleted: {key}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠ Key '{key}' not found{Style.RESET_ALL}")
    
    def do_keys(self, arg):
        """
        List all keys
        Usage: keys [pattern]
        
        Examples:
            keys
            keys user*
        """
        keys = self.storage.get_all_keys()
        
        if not keys:
            print(f"{Fore.YELLOW}No keys found{Style.RESET_ALL}")
            return
        
        # Filter by pattern if provided
        if arg:
            pattern = arg.strip()
            keys = [k for k in keys if pattern.replace('*', '') in k]
        
        print(f"{Fore.CYAN}Keys ({len(keys)} total):{Style.RESET_ALL}")
        for i, key in enumerate(keys, 1):
            print(f"  {i}. {key}")
    
    def do_info(self, arg):
        """
        Get information about a key
        Usage: info <key>
        
        Shows metadata like creation time, access count, TTL, etc.
        """
        if not arg:
            print(f"{Fore.RED}Error: Usage: info <key>{Style.RESET_ALL}")
            return
        
        key = arg.strip()
        entry = self.storage.get_entry(key)
        
        if entry:
            print(f"{Fore.CYAN}Information for key: {key}{Style.RESET_ALL}")
            print(f"  Value: {entry.value}")
            print(f"  Type: {entry.data_type}")
            print(f"  Created: {entry.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Last Accessed: {entry.last_accessed.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Access Count: {entry.access_count}")
            if entry.ttl:
                print(f"  TTL: {entry.ttl} seconds")
                if entry.expires_at:
                    print(f"  Expires: {entry.expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"{Fore.YELLOW}⚠ Key '{key}' not found{Style.RESET_ALL}")
    
    # ===== Cache Operations =====
    
    def do_cache_stats(self, arg):
        """Show cache statistics"""
        stats = self.cache.get_cache_stats()
        
        print(f"{Fore.CYAN}Cache Statistics:{Style.RESET_ALL}")
        print(f"  Size: {stats['cache_size']}/{stats['max_cache_size']}")
        print(f"  Utilization: {stats['cache_utilization']:.1f}%")
        print(f"  Hits: {stats['hits']}")
        print(f"  Misses: {stats['misses']}")
        print(f"  Hit Rate: {stats['hit_rate']:.2f}%")
        print(f"  Patterns Tracked: {stats['patterns_tracked']}")
        print(f"  Model Trained: {'Yes' if stats['model_trained'] else 'No'}")
    
    def do_cache_train(self, arg):
        """Train the predictive cache model"""
        print(f"{Fore.YELLOW}Training cache model...{Style.RESET_ALL}")
        success = self.cache.train_model()
        if success:
            print(f"{Fore.GREEN}✓ Model trained successfully{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Training failed (insufficient data){Style.RESET_ALL}")
    
    def do_cache_optimize(self, arg):
        """Optimize cache by pre-loading hot keys"""
        print(f"{Fore.YELLOW}Optimizing cache...{Style.RESET_ALL}")
        loaded = self.cache.optimize_cache(self.storage)
        print(f"{Fore.GREEN}✓ Pre-loaded {loaded} hot keys{Style.RESET_ALL}")
    
    def do_cache_hot_keys(self, arg):
        """Show keys predicted to be accessed soon"""
        hot_keys = self.cache.get_hot_keys(top_n=10)
        
        if not hot_keys:
            print(f"{Fore.YELLOW}No predictions available (train model first){Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}Top Hot Keys (predicted access likelihood):{Style.RESET_ALL}")
        for i, (key, likelihood) in enumerate(hot_keys, 1):
            bar_length = int(likelihood * 20)
            bar = '█' * bar_length + '░' * (20 - bar_length)
            print(f"  {i}. {key:20s} {bar} {likelihood:.2%}")
    
    def do_cache_clear(self, arg):
        """Clear the cache"""
        count = self.cache.clear_cache()
        print(f"{Fore.GREEN}✓ Cleared {count} cached entries{Style.RESET_ALL}")
    
    # ===== Anomaly Detection =====
    
    def do_anomalies(self, arg):
        """
        Show detected anomalies
        Usage: anomalies [severity]
        
        Examples:
            anomalies
            anomalies high
        """
        severity = arg.strip() if arg else None
        anomalies = self.anomaly_detector.get_anomalies(severity=severity)
        
        if not anomalies:
            print(f"{Fore.GREEN}✓ No anomalies detected{Style.RESET_ALL}")
            return
        
        print(f"{Fore.YELLOW}Detected Anomalies:{Style.RESET_ALL}")
        for anomaly in anomalies:
            color = Fore.RED if anomaly.severity == 'high' else Fore.YELLOW if anomaly.severity == 'medium' else Fore.BLUE
            print(f"\n  {color}[{anomaly.severity.upper()}] {anomaly.type}{Style.RESET_ALL}")
            print(f"  {anomaly.description}")
            print(f"  Detected: {anomaly.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            if anomaly.key:
                print(f"  Key: {anomaly.key}")
    
    def do_anomaly_check(self, arg):
        """Run full anomaly detection check"""
        print(f"{Fore.YELLOW}Running anomaly detection...{Style.RESET_ALL}")
        detected = self.anomaly_detector.run_full_check(self.storage)
        
        if detected:
            print(f"{Fore.YELLOW}⚠ Detected {len(detected)} new anomalies{Style.RESET_ALL}")
        else:
            print(f"{Fore.GREEN}✓ No new anomalies detected{Style.RESET_ALL}")
    
    # ===== Archive Operations =====
    
    def do_archive(self, arg):
        """
        Archive keys to compressed storage
        Usage: archive <key1> [key2] ... | archive cold
        
        Examples:
            archive old_data temp_file
            archive cold    (archives cold keys automatically)
        """
        if not arg:
            print(f"{Fore.RED}Error: Usage: archive <key1> [key2] ... | archive cold{Style.RESET_ALL}")
            return
        
        if arg.strip() == "cold":
            print(f"{Fore.YELLOW}Archiving cold keys...{Style.RESET_ALL}")
            count = self.archive_manager.archive_cold_keys(self.storage, self.cache)
            print(f"{Fore.GREEN}✓ Archived {count} cold keys{Style.RESET_ALL}")
        else:
            keys = arg.split()
            count = self.archive_manager.archive_keys(self.storage, keys)
            print(f"{Fore.GREEN}✓ Archived {count} keys{Style.RESET_ALL}")
    
    def do_restore(self, arg):
        """
        Restore archived keys
        Usage: restore [key1] [key2] ... | restore all
        
        Examples:
            restore old_data
            restore all
        """
        if arg.strip() == "all" or not arg:
            count = self.archive_manager.restore_keys(self.storage)
            print(f"{Fore.GREEN}✓ Restored {count} keys from archive{Style.RESET_ALL}")
        else:
            keys = arg.split()
            count = self.archive_manager.restore_keys(self.storage, keys)
            print(f"{Fore.GREEN}✓ Restored {count} keys from archive{Style.RESET_ALL}")
    
    def do_archive_list(self, arg):
        """List archived keys"""
        archived = self.archive_manager.list_archived_keys()
        
        if not archived:
            print(f"{Fore.YELLOW}No archived keys{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}Archived Keys ({len(archived)} total):{Style.RESET_ALL}")
        for i, item in enumerate(archived, 1):
            print(f"  {i}. {item['key']} (archived: {item['archived_at'][:19]})")
    
    # ===== Recovery Operations =====
    
    def do_checkpoint(self, arg):
        """Create a recovery checkpoint"""
        print(f"{Fore.YELLOW}Creating checkpoint...{Style.RESET_ALL}")
        success = self.recovery_manager.create_checkpoint(self.storage)
        if success:
            print(f"{Fore.GREEN}✓ Checkpoint created{Style.RESET_ALL}")
    
    def do_recovery_stats(self, arg):
        """Show recovery system statistics"""
        stats = self.recovery_manager.get_log_stats()
        
        print(f"{Fore.CYAN}Recovery System Statistics:{Style.RESET_ALL}")
        print(f"  Transaction Log Exists: {'Yes' if stats['log_exists'] else 'No'}")
        print(f"  Checkpoint Exists: {'Yes' if stats['checkpoint_exists'] else 'No'}")
        print(f"  Buffered Entries: {stats['buffered_entries']}")
        print(f"  Log Entries: {stats['log_entries']}")
        print(f"  Recovery Performed: {'Yes' if stats['recovery_performed'] else 'No'}")
    
    # ===== System Commands =====
    
    def do_stats(self, arg):
        """Show database statistics"""
        storage_stats = self.storage.get_stats()
        cache_stats = self.cache.get_cache_stats()
        anomaly_stats = self.anomaly_detector.get_stats()
        archive_stats = self.archive_manager.get_archive_stats()
        
        print(f"{Fore.CYAN}SmartStoreDB Statistics:{Style.RESET_ALL}\n")
        
        print(f"{Fore.YELLOW}Storage:{Style.RESET_ALL}")
        print(f"  Total Keys: {storage_stats['total_keys']}")
        print(f"  Total Accesses: {storage_stats['total_accesses']}")
        print(f"  Storage Size: {storage_stats['storage_size_mb']} MB")
        
        print(f"\n{Fore.YELLOW}Cache:{Style.RESET_ALL}")
        print(f"  Hit Rate: {cache_stats['hit_rate']:.2f}%")
        print(f"  Utilization: {cache_stats['cache_utilization']:.1f}%")
        print(f"  Model Trained: {'Yes' if cache_stats['model_trained'] else 'No'}")
        
        print(f"\n{Fore.YELLOW}Anomalies:{Style.RESET_ALL}")
        print(f"  Unresolved: {anomaly_stats['unresolved_anomalies']}")
        print(f"  High Severity: {anomaly_stats['high_severity']}")
        
        print(f"\n{Fore.YELLOW}Archive:{Style.RESET_ALL}")
        print(f"  Archived Keys: {archive_stats['archived_keys']}")
        print(f"  Archive Size: {archive_stats['archive_size_mb']} MB")
        if archive_stats['compression_ratio'] > 0:
            print(f"  Compression Ratio: {archive_stats['compression_ratio']:.2f}")
    
    def do_clear(self, arg):
        """Clear all data (requires confirmation)"""
        confirm = input(f"{Fore.RED}⚠ This will delete all data. Type 'YES' to confirm: {Style.RESET_ALL}")
        if confirm == "YES":
            count = self.storage.clear_all()
            self.cache.clear_cache()
            print(f"{Fore.GREEN}✓ Cleared {count} keys{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Operation cancelled{Style.RESET_ALL}")
    
    def do_exit(self, arg):
        """Exit SmartStoreDB"""
        print(f"\n{Fore.CYAN}Goodbye! SmartStoreDB shutting down...{Style.RESET_ALL}")
        return True
    
    def do_quit(self, arg):
        """Exit SmartStoreDB"""
        return self.do_exit(arg)
    
    def do_EOF(self, arg):
        """Exit on Ctrl+D"""
        return self.do_exit(arg)


def main():
    """Main entry point"""
    try:
        SmartStoreDBCLI().cmdloop()
    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}Goodbye!{Style.RESET_ALL}")
        sys.exit(0)


if __name__ == "__main__":
    main()
