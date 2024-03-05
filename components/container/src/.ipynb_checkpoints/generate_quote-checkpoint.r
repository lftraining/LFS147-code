#!/usr/bin/env Rscript

# Accept arguments from the command line
args <- commandArgs(trailingOnly = TRUE)
total_cost <- as.numeric(args[1])
state_tax_rate <- as.numeric(args[2])
output_path <- args[3] # The third argument is the output file path

# Calculate final price
final_price <- discounted_price * (1 + state_tax_rate)

# Scale the materials based on the total cost
scale_factor <- total_cost / 10000
magical_unicorns <- max(1, as.integer(15 * scale_factor))
dreamy_carriages <- max(1, as.integer(5 * scale_factor))
whimsical_music_boxes <- max(1, as.integer(1 * scale_factor))
rainbow_paint_gallons <- max(20, as.integer(20 * scale_factor))
stardust_glitter_pounds <- max(50, as.integer(50 * scale_factor))

# Construct the quote string
quote_string <- sprintf("Carousel Construction Quote:\nMagical Unicorns: %d\nDreamy Carriages: %d\nWhimsical Music Box: %d\nRainbow Paint (gallons): %d\nStardust Glitter (pounds): %d\nTotal Cost (with tax): $%.2f\n", magical_unicorns, dreamy_carriages, whimsical_music_boxes, rainbow_paint_gallons, stardust_glitter_pounds, final_price)

# Print the quote to the console
cat(quote_string)

# Write the quote string to the specified output file
writeLines(quote_string, output_path)
