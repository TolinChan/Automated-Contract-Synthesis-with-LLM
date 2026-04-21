1. 用两个agent分别输出spec对应代码和合约逻辑代码
   1. spec agent input: spec + 函数对应内容上下文；output: MOVE spec code
   2. contract agent input:  NL description + 函数签名; output: MOVE contract code
2. spec check agent: 用这个agent检查对于每个函数是否有遗漏spec（参考MSG的思路）
   1. 输入：MOVE spec code & MOVE contract code
   2. 输出：遗漏spec 返回给spec agent
                  无遗漏就输出true
3. 合约组装：把spec和contract拼起来
4. MOVE verifier：输入：拼装后的完整合约 输出：报错内容 or 通过
5. 错误处理agent：需要根据报错内容整理信息，把相关内容添加进函数对应内容上下文 & 合约描述