#!/bin/bash

# CID Comparison Tool Entrypoint Script
# This script provides a menu-driven interface for running CID comparison tools
# and keeps the container alive for interactive use.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to copy default configs if /app/configs is empty
populate_configs() {
    echo "Checking config directory..."
    
    # Check if /home/appuser/config is empty or doesn't contain our config files
    if [ ! -f "/home/appuser/config/dataset_config.json" ]; then
        echo "Populating /home/appuser/config with default configuration file..."
        
        # Ensure the directory exists and has proper permissions
        mkdir -p /home/appuser/config
        
        # Copy default configs if they exist (note: using .default-config with hyphen to match Dockerfile)
        if [ -d "/home/appuser/.default-config" ]; then
            cp -r /home/appuser/.default-config/* /home/appuser/config/ 2>/dev/null || true
            echo "Default configuration files copied to /home/appuser/config/"
        else
            echo "Warning: Default config directory /home/appuser/.default-config not found"
            # Debug: List what's actually in the home directory
            echo "Available directories in /home/appuser/:"
            ls -la /home/appuser/ | grep "default" || echo "No default directories found"
        fi
        
        # List what was copied
        echo "Configuration files available:"
        ls -la /home/appuser/config/ 2>/dev/null || echo "No files found in /home/appuser/config/"
    else
        echo "/home/appuser/config already contains configuration files. Skipping population."
    fi
}

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to display the main menu
show_menu() {
    clear
    echo "=================================================="
    echo "  CID Comparison Tool - Container Environment"
    echo "=================================================="
    echo ""
    echo "Available Commands:"
    echo ""
    echo "1) prepare-data     - Generate sample testing data"
    echo "2) setup-singularity - Initialize and prepare Singularity"
    echo "3) setup-ipfs       - Initialize and prepare IPFS"
    echo "4) compare-cids     - Compare CIDs between systems"
    echo "5) shell            - Open interactive bash shell"
    echo "6) status           - Check system status"
    echo "7) help             - Show detailed help"
    echo "8) exit             - Exit (stops container)"
    echo ""
    echo "Auto-run mode: Set CID_AUTO_RUN environment variable"
    echo "Examples:"
    echo "  CID_AUTO_RUN=prepare-data"
    echo "  CID_AUTO_RUN=full-pipeline"
    echo ""
    echo "=================================================="
}

# Function to check system status
check_status() {
    print_info "Checking system status..."
    echo ""
    
    # Check if sample data exists
    if [ -d "/data/sample_data" ] && [ "$(ls -A /data/sample_data 2>/dev/null)" ]; then
        print_success "Sample data: Available"
    else
        print_warning "Sample data: Not generated"
    fi
    
    # Check Singularity
    if command -v singularity &> /dev/null; then
        print_success "Singularity: Installed"
        if [ -f "/home/appuser/singularity.db" ]; then
            print_success "Singularity DB: Initialized"
        else
            print_warning "Singularity DB: Not initialized"
        fi
    else
        print_error "Singularity: Not found"
    fi
    
    # Check IPFS
    if command -v ipfs &> /dev/null; then
        print_success "IPFS: Installed"
        if [ -d "/home/appuser/.ipfs" ]; then
            print_success "IPFS: Initialized"
        else
            print_warning "IPFS: Not initialized"
        fi
    else
        print_error "IPFS: Not found"
    fi
    
    # Check for comparison results
    if [ -f "/data/comparison_output/comparison_report.txt" ]; then
        print_success "Latest comparison: Available"
        echo "  Location: /data/comparison_output/"
    else
        print_warning "Latest comparison: Not available"
    fi
    
    echo ""
}

# Function to run the full pipeline
run_full_pipeline() {
    print_info "Running full CID comparison pipeline..."
    
    print_info "Step 1: Generating sample data..."
    /home/appuser/scripts/prepare_testing_data.sh || {
        print_error "Failed to prepare testing data"
        return 1
    }
    
    print_info "Step 2: Setting up Singularity..."
    /home/appuser/scripts/singularity-prepare-content.sh || {
        print_error "Failed to setup Singularity"
        return 1
    }
    
    print_info "Step 3: Setting up IPFS..."
    /home/appuser/scripts/ipfs-prepare-content.sh || {
        print_error "Failed to setup IPFS"
        return 1
    }
    
    print_info "Step 4: Comparing CIDs..."
    /home/appuser/scripts/compare-cids.sh || {
        print_error "Failed to compare CIDs"
        return 1
    }
    
    print_success "Full pipeline completed successfully!"
    print_info "Results available in: /data/comparison_output/"
}

# Function to show detailed help
show_help() {
    echo ""
    echo "=== CID Comparison Tool Help ==="
    echo ""
    echo "This tool compares Content Identifier (CID) generation between"
    echo "Singularity and Kubo CLI (IPFS) implementations."
    echo ""
    echo "WORKFLOW:"
    echo "  1. Generate sample data using various file sizes and structures"
    echo "  2. Initialize Singularity with the sample data"
    echo "  3. Initialize IPFS and add the same sample data"
    echo "  4. Extract CIDs from both systems and compare them"
    echo ""
    echo "COMMANDS:"
    echo "  prepare-data     : Creates sample datasets with different file sizes"
    echo "  setup-singularity: Initializes Singularity DB and processes data"
    echo "  setup-ipfs      : Initializes IPFS datastore and adds content"
    echo "  compare-cids    : Extracts and compares CIDs from both systems"
    echo "  full-pipeline   : Runs all steps automatically"
    echo ""
    echo "DATA LOCATIONS:"
    echo "  /data/sample_data/     : Generated sample datasets"
    echo "  /data/output/          : Singularity output files"
    echo "  /data/comparison_output/ : Comparison results and reports"
    echo ""
    echo "ENVIRONMENT VARIABLES:"
    echo "  CID_AUTO_RUN          : Auto-run command on container start"
    echo "  GOLOG_LOG_LEVEL       : Singularity logging level"
    echo ""
    echo "INTERACTIVE MODE:"
    echo "  Use 'shell' command to get a bash prompt for manual operations"
    echo ""
}

# Function to handle auto-run mode
handle_auto_run() {
    case "$CID_AUTO_RUN" in
        "prepare-data"|"1")
            print_info "Auto-running: prepare-data"
            /home/appuser/scripts/prepare_testing_data.sh
            ;;
        "setup-singularity"|"2")
            print_info "Auto-running: setup-singularity"
            /home/appuser/scripts/singularity-prepare-content.sh
            ;;
        "setup-ipfs"|"3")
            print_info "Auto-running: setup-ipfs"
            /home/appuser/scripts/ipfs-prepare-content.sh
            ;;
        "compare-cids"|"4")
            print_info "Auto-running: compare-cids"
            /home/appuser/scripts/compare-cids.sh
            ;;
        "full-pipeline"|"full")
            print_info "Auto-running: full-pipeline"
            run_full_pipeline
            ;;
        "shell"|"5")
            print_info "Auto-running: shell"
            exec /bin/bash
            ;;
        *)
            print_warning "Unknown auto-run command: $CID_AUTO_RUN"
            ;;
    esac
}

# Main function
main() {
    # Handle command line arguments
    if [ $# -gt 0 ]; then
        case "$1" in
            "prepare-data"|"1")
                /home/appuser/scripts/prepare_testing_data.sh
                exit $?
                ;;
            "setup-singularity"|"2")
                /home/appuser/scripts/singularity-prepare-content.sh
                exit $?
                ;;
            "setup-ipfs"|"3")
                /home/appuser/scripts/ipfs-prepare-content.sh
                exit $?
                ;;
            "compare-cids"|"4")
                /home/appuser/scripts/compare-cids.sh
                exit $?
                ;;
            "shell"|"5")
                exec /bin/bash
                ;;
            "status"|"6")
                check_status
                exit 0
                ;;
            "help"|"7")
                show_help
                exit 0
                ;;
            "full-pipeline"|"full")
                run_full_pipeline
                exit $?
                ;;
            "menu")
                # Fall through to interactive menu
                ;;
            *)
                print_error "Unknown command: $1"
                echo "Use 'help' for available commands"
                exit 1
                ;;
        esac
    fi
    
    # Handle auto-run mode if set
    if [ -n "$CID_AUTO_RUN" ]; then
        handle_auto_run
        
        # If auto-run was not 'shell', continue to interactive mode
        if [ "$CID_AUTO_RUN" != "shell" ]; then
            print_info "Auto-run completed. Entering interactive mode..."
            echo "Press Enter to continue..."
            read
        fi
    fi
    
    # Interactive menu mode
    while true; do
        show_menu
        echo -n "Enter your choice (1-8): "
        read choice
        
        case $choice in
            1|"prepare-data")
                print_info "Running: prepare-data"
                /home/appuser/scripts/prepare_testing_data.sh
                echo ""
                echo "Press Enter to continue..."
                read
                ;;
            2|"setup-singularity")
                print_info "Running: setup-singularity"
                /home/appuser/scripts/singularity-prepare-content.sh
                echo ""
                echo "Press Enter to continue..."
                read
                ;;
            3|"setup-ipfs")
                print_info "Running: setup-ipfs"
                /home/appuser/scripts/ipfs-prepare-content.sh
                echo ""
                echo "Press Enter to continue..."
                read
                ;;
            4|"compare-cids")
                print_info "Running: compare-cids"
                /home/appuser/scripts/compare-cids.sh
                echo ""
                echo "Press Enter to continue..."
                read
                ;;
            5|"shell")
                print_info "Opening bash shell..."
                print_info "Type 'exit' to return to the menu"
                /bin/bash
                ;;
            6|"status")
                check_status
                echo "Press Enter to continue..."
                read
                ;;
            7|"help")
                show_help
                echo "Press Enter to continue..."
                read
                ;;
            8|"exit")
                print_info "Exiting CID Comparison Tool"
                exit 0
                ;;
            "full"|"full-pipeline")
                print_info "Running full pipeline..."
                run_full_pipeline
                echo ""
                echo "Press Enter to continue..."
                read
                ;;
            *)
                print_error "Invalid choice: $choice"
                echo "Press Enter to continue..."
                read
                ;;
        esac
    done
}

# Call the function to populate configs
populate_configs

# Trap signals to ensure clean shutdown
trap 'print_info "Received shutdown signal. Cleaning up..."; exit 0' SIGTERM SIGINT

# Start the main function
main "$@"