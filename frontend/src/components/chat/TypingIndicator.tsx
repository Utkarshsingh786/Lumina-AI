"use client";

import { motion } from "framer-motion";

/**
 * Animated typing indicator shown while waiting for first token.
 * Three dots with staggered pulse animation — standard "AI is thinking" pattern.
 */
export function TypingIndicator() {
  return (
    <div className="flex gap-3 px-4 py-3 mr-12">
      {/* Avatar */}
      <div className="w-8 h-8 rounded-full bg-neutral-700 flex-shrink-0 flex items-center justify-center text-xs mt-0.5">
        L
      </div>
      {/* Dots */}
      <div className="flex items-center gap-1 py-3 px-4 bg-neutral-800/50 rounded-2xl rounded-tl-sm">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            className="w-2 h-2 rounded-full bg-neutral-400"
            animate={{
              scale: [0.8, 1, 0.8],
              opacity: [0.5, 1, 0.5],
            }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              delay: i * 0.2,
            }}
          />
        ))}
      </div>
    </div>
  );
}
